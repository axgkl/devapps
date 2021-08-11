# Installing DevApps Derived Packages

Here is how applications derived from `devapps` are installed. It is actually a normal "pip install" - but you have to
configure the package server, which may be hosted on private Artifactory server.

> You will never `pip install devapps` standalone in a project but it will be installed as a *requirement* of derived packages.

Since installation steps are the same we lay them out here and refer to here from derived packages and applications.


## Package Server

Here are the different ways to configure a private package server.

### With pip

For a normal pip install do this:

```console
$ url="https://$user:$pass@artifacts.mycompany.com/artifactory/api/pypi/pypi/simple/" 
```


Then make sure your intended Python environment is active, see [Python installation](../python):

```console
$ pip install --user --index-url "$url" devapps 
```



### With [pipx](https://mycompany.com/pipxproject/pipx)

```console
$ pip install --user pipx # if you not yet have it
$ url="https://$user:$pass@artifacts.mycompany.com/artifactory/api/pypi/pypi/simple/" 
$ pipx install --index-url "$url" devapps # --verbose

```

### With [poetry](https://python-poetry.org/)

Poetry is the build and dependency management system, which all devapps are built with.  
This way enables you to run e.g. tests, since all development and test dependencies will be installed as well. 


> See [here](https://python-poetry.org/docs/repositories/) regarding repo access configuration. 

Here the steps:

### Configure Credentials

Configure artifactory credentials for python packages like so:

Example:

```console
$ poetry config repositories.ax "https://artifacts.mycompany.com/artifactory/api/pypi/pypi-ax-sources/simple/"
# using an *encrypted* password, will be stored in plain text w/o password manager:
$ poetry config http-basic.ax myusername xP6xCi3xxxxxxxxxxxxxxxxxxxx 
```

pyproject.toml:

```toml
[[tool.poetry.source]]
name = "ax"
url = "https://artifacts.mycompany.com/artifactory/api/pypi/pypi-ax-sources/simple"
secondary = true
```

Or manually:


```ini
$ cat $HOME/.config/pypoetry/auth.toml # on Linux. OSX / Windows: See poetry docs
[http-basic]
[http-basic.ax]
username = "myusername"
# use your encrypted password:
password = "aP6oxxxxxxxxxxxxxxxxxxxxuZSyr"

$ cat $HOME/.config/pypoetry/config.toml
[repositories]
[repositories.ax]
url = "https://artifacts.mycompany.com/artifactory/api/pypi/pypi-ax-sources/simple/"

```


Then, as for a [development install](../dev_inst) (i.e. with development packages installed).

```console
$ poetry install
```

