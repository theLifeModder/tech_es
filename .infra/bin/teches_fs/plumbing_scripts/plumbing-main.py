import os
import sys
import click

class TechesCliGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args:
            click.echo("error! You need to specify a valid argument.", err=True)
            ctx.exit(1)
        return super().parse_args(ctx, args)

@click.group(cls=TechesCliGroup)
def cli():
    """Teches File System Automation Tool Suite"""
    pass

@cli.command(name="fs")
@click.option("-e", "--edit", "edit_file", type=click.Path(), help="Open file in target instance editor.")
def fs_command(edit_file):
    """Handles the plumbing routing for file system management."""
    if not edit_file:
        click.echo("error! You need to specify a valid argument.", err=True)
        sys.exit(1)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    actions_path = os.path.abspath(os.path.join(current_dir, "../actions/edit"))
    
    sys.path.insert(0, actions_path)
    
    try:
        edit_module = __import__("teches-fs-edit")
        edit_module.open_editor(edit_file)
    except ImportError as e:
        click.echo(f"System Error: Failed to resolve core actions module. {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    cli()
