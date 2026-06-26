"""Base component with async lifecycle and dependency injection."""

import asyncio
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from ..enumeration import ComponentEnum
from ..utils import get_logger

if TYPE_CHECKING:
    from .application_context import ApplicationContext

T = TypeVar("T", bound="BaseComponent")


class ComponentMixin:
    """Shared state for components and steps: identity, config, workspace paths."""

    component_type = ComponentEnum.BASE

    def __init__(
        self,
        name: str | None = None,
        backend: str = "",
        app_context: "ApplicationContext | None" = None,
        **kwargs,
    ) -> None:
        self.name: str = name or self.__class__.__name__
        self.backend: str = backend
        self.app_context: "ApplicationContext | None" = app_context
        self.kwargs: dict = dict(kwargs)
        logger = get_logger()
        self.logger = logger.bind(component=self.name) if hasattr(logger, "bind") else logger

    @property
    def workspace_path(self) -> Path:
        """Workspace root (cwd when no app_context)."""
        if self.app_context is None:
            return Path.cwd()
        return Path(self.app_context.app_config.workspace_dir).absolute()

    def to_workspace_relative(self, path: str | Path) -> str:
        """Convert path to workspace-relative; return absolute when outside."""
        abs_path = Path(path).absolute()
        try:
            return str(abs_path.relative_to(self.workspace_path))
        except ValueError:
            return str(abs_path)


class Dependency:
    """Unresolved dependency placeholder; resolved on start(), errors on premature access."""

    __slots__ = ("ctype", "name", "default_factory", "optional")

    def __init__(
        self,
        ctype: ComponentEnum,
        name: str,
        default_factory: Callable[[], Any] | None = None,
        optional: bool = True,
    ) -> None:
        self.ctype, self.name, self.default_factory, self.optional = ctype, name, default_factory, optional

    def __repr__(self) -> str:
        return f"<unresolved {self.ctype.value}:{self.name}{'?' if self.optional else ''}>"

    def __getattr__(self, item: str) -> Any:
        raise RuntimeError(f"Dependency {self.ctype.value}:{self.name} accessed before start() (attribute '{item}')")


class BaseComponent(ComponentMixin, ABC):
    """Async lifecycle base with bind-based dependency injection."""

    component_type = ComponentEnum.BASE

    def __init__(
        self,
        name: str | None = None,
        backend: str = "",
        app_context: "ApplicationContext | None" = None,
        **kwargs,
    ) -> None:
        super().__init__(name=name, backend=backend, app_context=app_context, **kwargs)
        self._is_started: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._owned: list["BaseComponent"] = []  # components created via bind() default_factory

    @property
    def is_started(self) -> bool:
        """Whether the component has been started."""
        return self._is_started

    @staticmethod
    def bind(
        name: str | None,
        base_cls: type[T],
        *,
        default_factory: Callable[[], T] | None = None,
        optional: bool = True,
    ) -> T | None:
        """Declare a dependency; returns a Dependency placeholder resolved on start()."""
        if not name:
            return None
        ctype = getattr(base_cls, "component_type", None)
        if not isinstance(ctype, ComponentEnum) or ctype is ComponentEnum.BASE:
            raise TypeError(f"{base_cls.__name__} must declare a non-BASE ComponentEnum 'component_type'")
        return cast(T, Dependency(ctype, name, default_factory, optional))

    @property
    def dependencies(self) -> list[Dependency]:
        """List of unresolved Dependency placeholders."""
        return [v for v in self.__dict__.values() if isinstance(v, Dependency)]

    async def _resolve_bindings(self) -> None:
        for attr, dep in list(self.__dict__.items()):
            if isinstance(dep, Dependency):
                self._resolve_one(attr, dep)

    def _resolve_one(self, attr: str, dep: Dependency) -> None:
        if self.app_context is None:
            self._resolve_standalone(attr, dep)
        else:
            self._resolve_from_context(attr, dep)

    def _resolve_standalone(self, attr: str, dep: Dependency) -> None:
        """Standalone: use default_factory or None; required deps keep placeholder for clear errors."""
        if dep.default_factory is not None:
            instance = dep.default_factory()
            setattr(self, attr, instance)
            if isinstance(instance, BaseComponent):
                self._owned.append(instance)
        elif dep.optional:
            setattr(self, attr, None)

    def _resolve_from_context(self, attr: str, dep: Dependency) -> None:
        target = self.app_context.components.get(dep.ctype, {}).get(dep.name)
        if target is not None:
            setattr(self, attr, target)
        elif dep.optional:
            setattr(self, attr, None)
        else:
            raise ValueError(f"{dep.ctype.value} '{dep.name}' not found.")

    @property
    def workspace_metadata_path(self) -> Path:
        """Root directory for workspace metadata."""
        if self.app_context is None:
            return Path.cwd() / "metadata"
        return self.workspace_path / self.app_context.app_config.metadata_dir

    @property
    def component_metadata_path(self) -> Path:
        """Metadata directory for this component type."""
        return self.workspace_metadata_path / self.component_type.value

    async def _start(self) -> None:
        """Subclass hook after deps resolved."""

    async def _close(self) -> None:
        """Subclass hook during close."""

    async def dump(self) -> None:
        """Persist state to disk."""

    async def load(self) -> None:
        """Restore state from disk."""

    async def start(self) -> None:
        """Resolve deps → start owned → run _start."""
        async with self._lock:
            if self._is_started:
                return
            await self._resolve_bindings()
            for owned in self._owned:
                await owned.start()
            await self._start()
            self._is_started = True

    async def close(self) -> None:
        """Run _close → close owned in reverse order."""
        async with self._lock:
            if not self._is_started:
                return
            first_error: BaseException | None = None
            try:
                await self._close()
            except BaseException as exc:
                first_error = exc
            finally:
                for owned in reversed(self._owned):
                    try:
                        await owned.close()
                    except BaseException as exc:
                        if first_error is None:
                            first_error = exc
                        else:
                            self.logger.exception(f"Failed to close owned component {owned.name}: {exc}")
                self._is_started = False
            if first_error is not None:
                raise first_error

    async def restart(self) -> None:
        """Close and restart the component."""
        await self.close()
        await self.start()

    async def __call__(self, **kwargs):
        raise NotImplementedError

    async def __aenter__(self) -> "BaseComponent":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
