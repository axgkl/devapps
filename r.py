i = 'asdfa'
from rich import print
from rich.panel import Panel

p1 = Panel('Hello, [red]World!', title='Welcome', subtitle='Thank you')
print(Panel(p1 + p1, title='Welcome', subtitle='Thank you'))
