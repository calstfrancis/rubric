"""git_sync against real local repos (a bare 'remote' + two clones)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from rubric_package.utils import git_sync


def g(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "commit.gpgsign=false", *a],
                          capture_output=True, text=True, check=True)


def init(path, remote=None):
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    if remote:
        g(path, "remote", "add", "origin", str(remote))


class GitSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        env = {"GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"),
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        def restore():
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        self.remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        self.a, self.b = self.tmp / "a", self.tmp / "b"
        for d in (self.a, self.b):
            init(d, self.remote)
        (self.a / "one.liturgy").write_text("1\n")
        self.assertEqual(git_sync.commit_local(str(self.a), "first"), (True, ""))
        g(self.a, "push", "-u", "origin", "main")
        g(self.b, "pull", "origin", "main")
        g(self.b, "branch", "--set-upstream-to=origin/main")

    def commit(self, d, name, text):
        (d / name).write_text(text)
        git_sync.commit_local(str(d), name)

    def test_diverged_pull_merges_even_with_rebase_config(self):
        a, b = self.a, self.b
        g(a, "config", "pull.rebase", "true")
        self.commit(a, "two.liturgy", "a\n")
        self.commit(b, "three.liturgy", "b\n")
        self.assertEqual(git_sync.push(str(b)).status, git_sync.OK)
        res = git_sync.pull(str(a))
        self.assertEqual(res.status, git_sync.OK)
        self.assertTrue(res.changed)
        self.assertTrue((a / "three.liturgy").exists() and (a / "two.liturgy").exists())
        self.assertEqual(git_sync.push(str(a)).status, git_sync.OK)

    def test_same_file_edited_twice_conflicts(self):
        self.commit(self.b, "one.liturgy", "B\n"); git_sync.push(str(self.b))
        (self.a / "one.liturgy").write_text("dirty on a\n")   # uncommitted
        git_sync.commit_local(str(self.a), "a")
        self.assertEqual(git_sync.pull(str(self.a)).status, git_sync.CONFLICT)

    def test_conflict_then_leftover_merge_then_finish(self):
        a = self.a
        self.commit(self.b, "one.liturgy", "B\n"); git_sync.push(str(self.b))
        self.commit(a, "one.liturgy", "A\n")
        self.assertEqual(git_sync.pull(str(a)).status, git_sync.CONFLICT)
        self.assertTrue(git_sync.merge_in_progress(str(a)))
        self.assertEqual(git_sync.pull(str(a)).status, git_sync.CONFLICT)
        g(a, "checkout", "--ours", "one.liturgy"); g(a, "add", "one.liturgy")
        self.assertEqual(git_sync.pull(str(a)).status, git_sync.OK)
        self.assertFalse(git_sync.merge_in_progress(str(a)))
        self.assertEqual(git_sync.push(str(a)).status, git_sync.OK)

    def test_unrelated_histories_merge(self):
        c = self.tmp / "c"
        init(c, self.remote)
        self.commit(c, "local.liturgy", "x\n")
        res = git_sync.pull(str(c))
        self.assertEqual(res.status, git_sync.OK, res)
        self.assertTrue((c / "one.liturgy").exists() and (c / "local.liturgy").exists())

    def test_push_rejected_retries_after_pull(self):
        self.commit(self.b, "b.liturgy", "b\n"); git_sync.push(str(self.b))
        self.commit(self.a, "a.liturgy", "a\n")
        self.assertEqual(git_sync.push(str(self.a)).status, git_sync.OK)
        self.assertTrue((self.a / "b.liturgy").exists())

    def test_no_remote(self):
        d = self.tmp / "solo"
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        self.assertEqual(git_sync.pull(str(d)).status, git_sync.NO_REMOTE)


if __name__ == "__main__":
    unittest.main()
