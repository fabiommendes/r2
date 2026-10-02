from rich.console import Console
from rich.style import Style

style = Style()

plain = Console(highlight=False, markup=False, style=style)
plain_error = Console(stderr=True, highlight=False, markup=False, style=style)
stdout = Console(highlight=False, style=style)
stderr = Console(stderr=True, highlight=False, style=style)
