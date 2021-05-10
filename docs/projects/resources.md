# Resources

DevApps should work cross OS and distributions and often depend on interplaying with processes and tools *not* written in
Python - sometimes significantly customized, like Node-RED for the [lc-python](http://pages.github.com/lc-python/) based Low Code application family.

!!! hint
    Such tools might be (command line) utilities like [`rg`](https://blog.burntsushi.net/ripgrep/) and [`fzf`](https://www.youtube.com/watch?v=Bww2iaMTZRI) but also databases like redis or mysql.

This section explains which technologies and tools DevApps provides and why - in order to deliver a 'just works by default' user experience.

!!! note "Batteries included but Replaceable"

    There is no need for the user to use these technologies, when there are better suited alternatives in his working environment, e.g. native packages or containers.


## Preliminary Considerations

Applications are typically distributed over the filesystem in various places:

1. The actual binaries and libraries of the app itself
1. The dependencies of the app (libraries)
1. The app configuration, which might include custom code
1. Logs, data, temporary files

And the same for all resources, e.g. databases which the app requires to run.

The specific ways how resources and their dependencies are arranged within the system depends on the OS (Linux vs BSDs vs OSx vs Windows) but even within OS distributions and versions.

Devapps based applications give the user the option to keep all that together:

```
├── app_python libs_and_executables (products)
│   └── <in the virtual python environment>
│
├── app_project_folder
│   ├── bin
│   │   └── <e.g. redis-server start wrapper>
│   ├── conf
│   ├── data
│   ├── tmp
│   ├── <usually within HOME folder>
│   └── work
│
└── third party app_resources (conda, filesystems)
    ├── conda env:_resource_one
    │   └── <e.g. redis>
    ├── conda env:_resource_two
    │   └── <e.g. mysql>
    └── fs 
        └── <complete filesystem for resource 3>
 
```

In development mode, i.e. when you work with a clone of a specific devapps based repo, then

- the project folder and the poetry environment of the devapps lib under development may be identical
- the resources directory may also be contained within that directory. Often more practical is, to keep those elsewhere, for re-usability reasons


## Technology Choices / Resource Types

Currently devapp manages the following resource types:

#### Filesystem

This allows to pull whole filesystems layer by layer from container reqistries and have them put together locally using tar, without
the need for root permissions or the presence of container tools.

Tools and daemons within those filesystems are usable, often w/o the need to run within the prefix (e.g. `$LD_LIBRARY_PATH` is often enough, i.e. then w/o chroot permissions).  


### Conda

As already mentioned, binary packages from the Anaconda ecosystem allow to install resources, 100% compliant with the goals
stated above:

- Distribution independent
- Cross platform binary packages
- Installable in different versions
- W/o root permissions
- W/o affecting the file system outside a configurable prefix.

After installation the resources are completely contained within `$HOME/miniconda3/envs/<resource name>` and can be deleted by removing the `envs/<resource name>` directories.




Downsides:

- Not all is available yet, the ecosystem is smaller, compared to big distributions like Debian
- Less reliable long term maintenance - much smaller community. Currently the third party [conda forge](https://conda-forge.org/) channel maintains the biggest packages index.

!!! important "Conda is the technology of choice for third party tools and services"
    For the *batteries included but replaceable*[1] approach, we consider the advantages to outweigh the disadvantages and therefore the `devapps` included tool to install resources is using Conda as primary packaging system.   

    [1] e.g. in production environments

In the next chapter you'll learn how the `ops project` tool allows to create projects and have resources installed. 


