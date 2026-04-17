R2
== 

R2 is a non-IA personal computer assistant. I assume this project is not useful
for anyone else but me, but feel free to fork it if you want to use it as
inspiration.

It assumes some things about your setup:

- I use Nix Packages on Debian Trixie.
- I use Chezmoi to manage my dotfiles.
- I use GNOME as my main desktop environment.
- I use UV to manage Python and all Python apps (including this) in my system.
- It sometime assumes some specific applications are installed.


Usage
=====

Either `pip install r2-assistant` or install UV and create an alias in your
shell configuration like this:

```sh
alias r2="uvx --from r2-assistant r2"
```

Then you can run R2 with:

```sh
r2
```


Commands
========

**`r2 hd <PATH>`** 

Move a file or directory to the hard drive path. My setup
has a hard drive mounted at `~/hd`, and I use this command to move files there
when I want to free up space on my main SSD drive.

**`r2 alias <ALIAS> <COMMAND>`**

Create a shell alias. This is useful for creating shortcuts for commands I use often.
The setup assumes the existence of a file `~/.bash_aliases` where these aliases 
are stored. It also assumes the file has a specific format, with a section for R2 aliases that looks like this:

```sh
# R2 Aliases
alias ll='ls -la'
alias gs='git status'
```

`r2 alias` will add a new alias to some specific section (or the fallback
"other", if not given). It will also check for duplicates before adding a new
alias. 

It also has special support for aliasing Python packages (using uv) or
Javascript packages (using npx).