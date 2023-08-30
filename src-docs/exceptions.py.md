<!-- markdownlint-disable -->

<a href="../src/exceptions.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `exceptions.py`
User-defined exceptions used by WordPress charm. 



---

## <kbd>class</kbd> `WordPressBlockedStatusException`
Same as :exc:`exceptions.WordPressStatusException`. 

<a href="../src/exceptions.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize the instance. 



**Args:**
 
 - <b>`message`</b>:  A message explaining the reason for given exception. 



**Raises:**
 
 - <b>`TypeError`</b>:  if same base class is used to instantiate base class. 





---

## <kbd>class</kbd> `WordPressInstallError`
Exception for unrecoverable errors during WordPress installation. 





---

## <kbd>class</kbd> `WordPressMaintenanceStatusException`
Same as :exc:`exceptions.WordPressStatusException`. 

<a href="../src/exceptions.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize the instance. 



**Args:**
 
 - <b>`message`</b>:  A message explaining the reason for given exception. 



**Raises:**
 
 - <b>`TypeError`</b>:  if same base class is used to instantiate base class. 





---

## <kbd>class</kbd> `WordPressStatusException`
Exception to signal an early termination of the reconciliation. 

``status`` represents the status change comes with the early termination. Do not instantiate this class directly, use subclass instead. 

<a href="../src/exceptions.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize the instance. 



**Args:**
 
 - <b>`message`</b>:  A message explaining the reason for given exception. 



**Raises:**
 
 - <b>`TypeError`</b>:  if same base class is used to instantiate base class. 





---

## <kbd>class</kbd> `WordPressWaitingStatusException`
Same as :exc:`exceptions.WordPressStatusException`. 

<a href="../src/exceptions.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize the instance. 



**Args:**
 
 - <b>`message`</b>:  A message explaining the reason for given exception. 



**Raises:**
 
 - <b>`TypeError`</b>:  if same base class is used to instantiate base class. 





