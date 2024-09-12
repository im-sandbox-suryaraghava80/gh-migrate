# Contributing

`gh migrate` is a [GitHub CLI extension]() implemented using Python and the [Click CLI library]().

## Adding Commands

Commands are defined in the `migrate/commands` directory.

Adding a new command typically requires the following steps:

## Step 1

Create `migrate/commands/foo.py` containing:

```python
import click

@click.command()
@click.argument("arg1", required=True)
def foo(arg1):
    print(f"*** fooing some {arg1}")
    return
```

## Step 2

Update `migrate/__main__.py`:

```python
import click
...
from .commands.foo import foo # Added


@click.group()
def cli():
    pass


cli.add_command(diff)
...
cli.add_command(foo) # Added

if __name__ == "__main__":
    cli()
```
