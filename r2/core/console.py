from rich.console import Console
from rich.style import Style

style = Style()

# soft_wrap: never fold long lines, agents and pipes want one record per line.
plain = Console(highlight=False, markup=False, style=style, soft_wrap=True)
plain_error = Console(
    stderr=True, highlight=False, markup=False, style=style, soft_wrap=True
)
stdout = Console(highlight=False, style=style, soft_wrap=True)
stderr = Console(stderr=True, highlight=False, style=style, soft_wrap=True)
