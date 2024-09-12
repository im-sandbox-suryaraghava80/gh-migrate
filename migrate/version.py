import os
import functools
from git import Repo
from loguru import logger


def get_branch(branch="engagement"):
    repo = Repo(".")

    if branch in repo.heads:
        repo.heads.engagement.checkout()
    else:
        raise Exception(f"Branch {branch} does not exist")

    return repo


def checkpoint_file(file_path, message):
    repo = get_branch()

    if os.path.exists(file_path):
        repo.index.add([file_path])
        repo.index.commit(message)


def snapshot_before_after():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            repo = Repo(".")

            # Check if engagement branch already exists
            if "engagement" in repo.heads:
                logger.info("*** Switching to engagement branch")
                repo.heads.engagement.checkout()
            else:
                logger.info("*** Creating engagement branch")
                repo.create_head("engagement")
                repo.heads.engagement.checkout()

            # Commit all untracked and modified files
            untracked_files = repo.untracked_files
            modified_files = [item.a_path for item in repo.index.diff(None)]
            repo.index.add(untracked_files + modified_files)
            repo.index.commit(f"{func.__name__}: Before snapshot")

            result = func(*args, **kwargs)

            # Commit all untracked and modified files
            untracked_files = repo.untracked_files
            modified_files = [item.a_path for item in repo.index.diff(None)]
            repo.index.add(untracked_files + modified_files)
            repo.index.commit(f"{func.__name__}: After snapshot")

            return result

        return wrapper

    return decorator
