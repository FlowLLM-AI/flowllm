from typing import List


class BaseContext:
    def __init__(self, **kwargs):
        self._data = {**kwargs}

    def __getattr__(self, name: str):
        if name in self._data:
            return self._data[name]

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        if name == "_data":
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __getitem__(self, name: str):
        if name not in self._data:
            raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")
        return self._data[name]

    def __setitem__(self, name: str, value):
        self._data[name] = value

    def __contains__(self, name: str):
        return name in self._data

    def __repr__(self):
        return f"{self.__class__.__name__}({self._data!r})"

    def dump(self) -> dict:
        return self._data

    @property
    def keys(self) -> List[str]:
        return sorted(self._data.keys())

    def update(self, **kwargs):
        self._data.update(kwargs)


if __name__ == "__main__":
    ctx = BaseContext(**{"name": "Alice", "age": 30, "city": "New York"})

    print(ctx.name)
    print(ctx.age)
    print(ctx.city)

    ctx.email = "alice@example.com"
    ctx["email"] = "alice@example.com"
    print(ctx.email)

    print(ctx.keys)
    print(ctx)

    # print(ctx.city2)
