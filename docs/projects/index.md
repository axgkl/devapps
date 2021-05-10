# Projects

During the previous sections you learned how to install the application libs and executables.

After you installed Python and a DevApps application package (with its dependencies) either in pip(x) production or poetry development mode, you can now create and maintain
projects, i.e. directories, where additional project specific files are kept.

These can be...

- config files
- additional code
- specific executables
- secret stores
- log and data directories

...and so on.


- The directory of projects is arbitrary, e.g. `$HOME/myproject`
- In real projects it is typically tracked in large parts via git.


!!! hint
    When you develop on a *product package*, then that directory can be kept identical with the product repo directory
    itself, while developping.


The `devapps` base repo installs a tool (`ops`), which assists at creation and normalization of projects.

Before we explain that tool, we first highlight the basics of DevApps **resources**. 


