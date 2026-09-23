from .Puffin1 import Puffin1, Puffin1Params


Puffin4Params = Puffin1Params


class Puffin4(Puffin1):
    def __init__(self, **kwargs):
        kwargs["name"] = "Puffin4"
        super().__init__(**kwargs)