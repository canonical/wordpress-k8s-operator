<!-- markdownlint-disable -->

<a href="../src/types_.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `types_.py`
Module for commonly used internal types in WordPress charm. 



---

## <kbd>class</kbd> `CommandExecResult`
Result of executed command from WordPress container. 

Attrs:  return_code: exit code from executed command.  stdout: standard output from the executed command.  stderr: standard error output from the executed command. 





---

## <kbd>class</kbd> `DatabaseConfig`
Configuration values required to connect to database. 

Attrs:  hostname: The hostname under which the database is being served.  database: The name of the database to connect to.  username: The username to use to authenticate to the database.  password: The password to use to authenticat to the database. 





---

## <kbd>class</kbd> `ExecResult`
Wrapper for executed command result from WordPress container. 

Attrs:  success: True if command successful, else False.  result: returned value from execution command, parsed in desired format.  message: error message output of executed command. 





