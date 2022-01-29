gitnotekv is a Python package to use Git notes as a key-value store.

# Usage
Git notes are set on specific commits. Here is the basic usage:
```python
import gitnotekv

with gitnotekv.Repo('repo_path_here') as repo:
    ref = repo['reference'] # This can be a git hash, branch, tag, etc.
    ref['key1'] = 'value1'
    ref['key2'] = 'value2'
    print(ref['key1'], ref['key2']) # Prints "value1 value2"
# The new note values will be committed to the repo here
```

By default, note updates will only be committed locally. In order to have the notes pushed remotely, specify the `remote_push` flag when creating the Repo object:
```python
with gitnotekv.Repo('repo_path_here', remote_push=True) as repo:
    ref = repo['reference']
    ref['key1'] = 'value1'
# Note updates will be committed and pushed to remote here
```

Each note is stored as a JSON object, so all JSON data types are allowed. This means that more levels of key nesting is possible by storing dictionaries as key values:
```python
with gitnotekv.Repo('repo_path_here') as repo:
    ref = repo['reference']
    ref['key1'] = {'hello': 'world'}
    print(ref['key1']['hello']) # Prints "world"
```

Note that note values are only updated when assigning back to the top level references:
```python
with gitnotekv.Repo('repo_path_here') as repo:
    ref = repo['reference']
    ref['key1'] = {'hello': 'world'}
    value = ref['key1']
    value['hello'] = 'world 2' # This does NOT update ref['key1']
    ref['key1'] = value # ref['key1'] is updated
```
