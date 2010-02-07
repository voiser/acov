
from acov import *

p = ProjectTree()
p.add("/new/version", "/old/version")
p.do_gcov()

