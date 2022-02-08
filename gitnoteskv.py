"""
The main module for using Git notes as a key-value store.

This module defines the classes for modeling Git repositories and individual
references within repositories. Each reference within a repository (for
example, a branch, tag, or commit hash) acts as a separate key-value store, to
which any number of key-value pairs can be written.
"""
import json
import sh


class RepoDoesNotExistError(Exception):
    """Exception class to signal when a repo doesn't exist."""


class GitReferenceDoesNotExistError(Exception):
    """
    Exception class for non-existent git references.

    This is to signal that the calling code has asked for a reference (branch,
    tag, git hash, etc.) that doesn't exist in a Git repo.

    """


class MalformedNoteDataError(Exception):
    """
    Exception class for malformed KV note data.

    The key-value pairs managed by this library are written to the Git repo as
    JSON strings. Whenever this library is expecting a value to be in note form
    but it is not, this exception is raised.
    """


class Repo:
    """
    Class to represent a single Git repository.

    This class is meant to be used with a `with` block, for example:

    with Repo('repo_path_here') as repo:
        <your note operations here>

    At the end of the `with` block, changes to the notes will be committed to
    the Git repo, and optionally pushed to remote.
    """

    def __init__(self, repo_path: str, remote_push: bool = False):
        """
        Instantiate a Repo object representing a single Git repo.

        :param repo_path: The file path to the Git repo.
        :type repo_path: str
        :param remote_push: A flag to indicate whether or not to push note
                           changes to remote upon commit. By default, this is
                           False.
        :type remote_push: bool
        """
        self.repo_path = repo_path
        self.remote_push = remote_push
        self.git = sh.git.bake('--no-pager', '-C', self.repo_path)

    def __enter__(self):
        """
        Entry function for using a Repo object in a `with` block.

        This function ensures that the Git repo exists.

        :raises RepoDoesNotExistError: When the Git repo doesn't exist.
        """
        try:
            self.git('rev-parse')
            self.active_refs = {}
        except sh.ErrorReturnCode_128:
            raise RepoDoesNotExistError(self.repo_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit function for using a Repo object in a `with` block.

        This function commits notes that have changed to the Git repo, deletes
        notes that have been removed, and pushes notes to remote if that was
        enabled when constructing the Repo object.
        """
        for repo_ref in self.active_refs.values():
            if repo_ref.note_kv:
                self.git.notes.add(
                    '-f', '-m', json.dumps(repo_ref.note_kv), repo_ref.ref)
            else:
                self.git.notes.remove('--ignore-missing', repo_ref.ref)

    def __getitem__(self, key: str):
        """
        Retrieve a RepoRef for a given reference (branch, tag, etc.).

        :param key: The reference name to retrieve.
        :type key: str
        :returns: An object to manipulate notes on the requested reference.
        :rtype: RepoRef
        """
        try:
            result = self.git('rev-parse', key)
            ref = str(result).strip()
            if ref in self.active_refs:
                return self.active_refs[ref]
            repo_ref = RepoRef(self, ref)
            self.active_refs[ref] = repo_ref
            return repo_ref
        except sh.ErrorReturnCode_128:
            raise GitReferenceDoesNotExistError(key)

    def __delete__(self, key):
        """
        Remove all key-value pairs associated with a Git reference.

        :param key: The Git reference whose KV pairs will be cleared.
        :type key: str
        """
        self[key].clear()


class RepoRef:
    """
    A class representing KV pairs under a Git reference in a repository.

    Objects of this class can be manipulated like a dictionary. Indexing into
    the object with a key will get the value stored in the Git note under the
    specific Git reference (branch, tag, commit hash, etc.) that the RepoRef
    object represents. Writing to that key will set the value for that
    key. Changes to the key-value pairs are not committed to the Git repo until
    the associated Repo object writes them at the end of its `with` block.

    This object should not be directly created by application code. Instead,
    they will be created by a Repo object when it is indexed on a Git
    reference. For example:

    with Repo('repo_path_here') as repo:
        ref = repo['main'] # ref is a RepoRef pointing to the main branch

    All keys in the KV for a RepoRef must be strings.
    """

    def __init__(self, repo: Repo, ref: str):
        """
        Initialize a RepoRef.

        :param repo: The Repo object to which this RepoRef belongs.
        :type repo: Repo
        :param ref: The Git reference (branch, tag, commit hash, etc.) whose
                    notes this RepoRef is being used to manipulate.
        """
        self.repo = repo
        self.ref = ref
        self.note_kv = {}
        try:
            note_data = str(self.repo.git.notes.show(self.ref))
        except sh.ErrorReturnCode_1:
            # No notes found for this reference
            return
        try:
            parsed = json.loads(note_data)
            if not isinstance(parsed, dict):
                raise MalformedNoteDataError(
                    f'Expected dict in note {ref}, found {type(parsed)}')
            self.note_kv = parsed
        except json.decoder.JSONDecodeError:
            raise MalformedNoteDataError(
                f'Could not parse {note_data} as JSON')

    def __getitem__(self, key: str):
        """
        Get the value associated with a key for this Git reference.

        :param key: The key whose value will be retrieved.
        :type key: str
        :returns: The value associated with the key.
        :rtype: Any JSON-mappable value (str, int, float, list, dict, None)
        :raises ValueError: When the key is a not a string
        :raises KeyError: When the key does not exist.
        """
        if not isinstance(key, str):
            raise ValueError(f'RepoRef key must be a string, got {type(key)}')
        return self.note_kv[key]

    def __setitem__(self, key: str, value):
        """
        Set the value associated with a key for this Git reference.

        :param key: The key whose value will be set.
        :type key: str
        :param value: The value to set.
        :type value: Any JSON-mappable value (str, int, float, list, dict,
                     None)
        :raises ValueError: When the key is not a string
        """
        if not isinstance(key, str):
            raise ValueError(f'RepoRef key must be a string, got {type(key)}')
        self.note_kv[key] = value

    def __contains__(self, key: str) -> bool:
        """
        Check if a key is set for this Git reference.

        :param key: The key for which to check.
        :type key: str
        :returns: Whether or not the key is set.
        :rtype: bool
        """
        return key in self.note_kv

    def __delitem__(self, key: str):
        """
        Delete a key-value pair.

        :param key: The key of the key-value pair to delete.
        :type key: str
        """
        del self.note_kv[key]

    def get(self, key: str, default=None):
        """
        Attempt to get the value for a key.

        If the key exists under the Git reference, return the value. If it
        doesn't exist, return the default value passed to this method.

        :param key: The key for the value to retrieve.
        :type key: str
        :param default: The value to return if the key does not exist.
        :type default: Any JSON-mappable value (str, int, float, list, dict,
                       None)
        :returns: The value of the key or the default if it doesn't exist.
        :rtype: Any JSON-mappable value (str, int, float, list, dict, None)
        :raises ValueError: If the key is not a string
        """
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self):
        """Clear all key-value pairs for this Git reference."""
        self.note_kv = {}
