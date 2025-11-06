R2
== 

My personal Computer assistant. I assume this project is not useful for anyone 
else but me, but feel free to fork it if you want to use it as inspiration.

It assumes some things about your setup:

- I use NixOS.
- I use Chezmoi to manage my dotfiles.
- I use GNOME as my main desktop environment.
- I use UV to manage Python and all Python apps (including this) in my system.
- It sometime assumes some specific applications are installed.


Usage
=====

Install UV and create an alias in your shell configuration like this:

```sh
alias r2="uv run --package r2-assistant r2"
```

Then you can run R2 with:

```sh
r2
```