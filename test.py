class A:
    val = None

    def __init__(self):
        self.val = "yes"

    def thing(self):
        print(self.__name__)


a = A()
