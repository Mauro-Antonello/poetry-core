import re
import subprocess

from collections import namedtuple
from pathlib import Path
from typing import Any
from typing import Optional

from poetry.core.utils._compat import WINDOWS


pattern_formats = {
    "protocol": r"\w+",
    "user": r"[a-zA-Z0-9_.-]+",
    "resource": r"[a-zA-Z0-9_.-]+",
    "port": r"\d+",
    "path": r"[\w~.\-/\\]+",
    "name": r"[\w~.\-]+",
    "rev": r"[^@#]+?",
    "subdir": r"[\w\-/\\]+",
}

PATTERNS = [
    re.compile(
        r"^(git\+)?"
        r"(?P<protocol>https?|git|ssh|rsync|file)://"
        r"(?:(?P<user>{user})@)?"
        r"(?P<resource>{resource})?"
        r"(:(?P<port>{port}))?"
        r"(?P<pathname>[:/\\]({path}[/\\])?"
        r"((?P<name>{name}?)(\.git|[/\\])?)?)"
        r"(?:"
        r"#egg=?.+"
        r"|"
        r"#(?:egg=.+?&subdirectory=|subdirectory=)(?P<subdirectory>{subdir})"
        r"|"
        r"[@#](?P<rev>{rev})(?:[&#](?:egg=.+?|(?:egg=.+?&subdirectory=|subdirectory=)(?P<rev_subdirectory>{subdir})))?"
        r")?"
        r"$".format(
            user=pattern_formats["user"],
            resource=pattern_formats["resource"],
            port=pattern_formats["port"],
            path=pattern_formats["path"],
            name=pattern_formats["name"],
            rev=pattern_formats["rev"],
            subdir=pattern_formats["subdir"],
        )
    ),
    re.compile(
        r"(git\+)?"
        r"((?P<protocol>{protocol})://)"
        r"(?:(?P<user>{user})@)?"
        r"(?P<resource>{resource}:?)"
        r"(:(?P<port>{port}))?"
        r"(?P<pathname>({path})"
        r"(?P<name>{name})(\.git|/)?)"
        r"(?:"
        r"#egg=?.+"
        r"|"
        r"#(?:egg=.+?&subdirectory=|subdirectory=)(?P<subdirectory>{subdir})"
        r"|"
        r"[@#](?P<rev>{rev})(?:[&#](?:egg=.+?|(?:egg=.+?&subdirectory=|subdirectory=)(?P<rev_subdirectory>{subdir})))?"
        r")?"
        r"$".format(
            protocol=pattern_formats["protocol"],
            user=pattern_formats["user"],
            resource=pattern_formats["resource"],
            port=pattern_formats["port"],
            path=pattern_formats["path"],
            name=pattern_formats["name"],
            rev=pattern_formats["rev"],
            subdir=pattern_formats["subdir"],
        )
    ),
    re.compile(
        r"^(?:(?P<user>{user})@)?"
        r"(?P<resource>{resource})"
        r"(:(?P<port>{port}))?"
        r"(?P<pathname>([:/]{path}/)"
        r"(?P<name>{name})(\.git|/)?)"
        r"(?:"
        r"#egg=.+?"
        r"|"
        r"#(?:egg=.+?&subdirectory=|subdirectory=)(?P<subdirectory>{subdir})"
        r"|"
        r"[@#](?P<rev>{rev})(?:[&#](?:egg=.+?&subdirectory=|subdirectory=)(?P<rev_subdirectory>{subdir}))?"
        r")?"
        r"$".format(
            user=pattern_formats["user"],
            resource=pattern_formats["resource"],
            port=pattern_formats["port"],
            path=pattern_formats["path"],
            name=pattern_formats["name"],
            rev=pattern_formats["rev"],
            subdir=pattern_formats["subdir"],
        )
    ),
    re.compile(
        r"((?P<user>{user})@)?"
        r"(?P<resource>{resource})"
        r"[:/]{{1,2}}"
        r"(?P<pathname>({path})"
        r"(?P<name>{name})(\.git|/)?)"
        r"(?:"
        r"#egg=?.+"
        r"|"
        r"#(?:egg=.+?&subdirectory=|subdirectory=)(?P<subdirectory>{subdir})"
        r"|"
        r"[@#](?P<rev>{rev})(?:[&#](?:egg=.+?|(?:egg=.+?&subdirectory=|subdirectory=)(?P<rev_subdirectory>{subdir})))?"
        r")?"
        r"$".format(
            user=pattern_formats["user"],
            resource=pattern_formats["resource"],
            path=pattern_formats["path"],
            name=pattern_formats["name"],
            rev=pattern_formats["rev"],
            subdir=pattern_formats["subdir"],
        )
    ),
]


class GitError(RuntimeError):

    pass


class ParsedUrl:
    def __init__(
        self,
        protocol: Optional[str],
        resource: Optional[str],
        pathname: Optional[str],
        user: Optional[str],
        port: Optional[str],
        name: Optional[str],
        rev: Optional[str],
        subdirectory: Optional[str] = None,
    ):
        self.protocol = protocol
        self.resource = resource
        self.pathname = pathname
        self.user = user
        self.port = port
        self.name = name
        self.rev = rev
        self.subdirectory = subdirectory

    @classmethod
    def parse(cls, url: str) -> "ParsedUrl":
        for pattern in PATTERNS:
            m = pattern.match(url)
            if m:
                groups = m.groupdict()
                return ParsedUrl(
                    groups.get("protocol"),
                    groups.get("resource"),
                    groups.get("pathname"),
                    groups.get("user"),
                    groups.get("port"),
                    groups.get("name"),
                    groups.get("rev"),
                    groups.get("rev_subdirectory") or groups.get("subdirectory"),
                )

        raise ValueError(f'Invalid git url "{url}"')

    @property
    def url(self) -> str:
        return "{}{}{}{}{}".format(
            f"{self.protocol}://" if self.protocol else "",
            f"{self.user}@" if self.user else "",
            self.resource,
            f":{self.port}" if self.port else "",
            "/" + (self.pathname or "").lstrip(":/"),
        )

    def format(self) -> str:
        return self.url

    def __str__(self) -> str:
        return self.format()


GitUrl = namedtuple("GitUrl", ["url", "revision", "subdirectory"])


_executable: Optional[str] = None


def executable() -> str:
    global _executable

    if _executable is not None:
        return _executable

    if WINDOWS:
        # Finding git via where.exe
        where = "%WINDIR%\\System32\\where.exe"
        paths = subprocess.check_output(
            [where, "git"], shell=True, encoding="oem"
        ).split("\n")
        for path in paths:
            if not path:
                continue

            _path = Path(path.strip())
            try:
                _path.relative_to(Path.cwd())
            except ValueError:
                _executable = str(_path)

                break
    else:
        _executable = "git"

    if _executable is None:
        raise RuntimeError("Unable to find a valid git executable")

    return _executable


def _reset_executable() -> None:
    global _executable

    _executable = None


class GitConfig:
    def __init__(self, requires_git_presence: bool = False) -> None:
        self._config = {}

        try:
            config_list = subprocess.check_output(
                [executable(), "config", "-l"], stderr=subprocess.STDOUT
            ).decode()

            m = re.findall("(?ms)^([^=]+)=(.*?)$", config_list)
            if m:
                for group in m:
                    self._config[group[0]] = group[1]
        except (subprocess.CalledProcessError, OSError):
            if requires_git_presence:
                raise

    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        return self._config.get(key, default)

    def __getitem__(self, item: Any) -> Any:
        return self._config[item]


class Git:
    def __init__(self, work_dir: Optional[Path] = None) -> None:
        self._config = GitConfig(requires_git_presence=True)
        self._work_dir = work_dir

    @classmethod
    def normalize_url(cls, url: str) -> GitUrl:
        parsed = ParsedUrl.parse(url)

        formatted = re.sub(r"^git\+", "", url)
        if parsed.rev:
            formatted = re.sub(fr"[#@]{parsed.rev}$", "", formatted)

        if parsed.subdirectory:
            formatted = re.sub(
                fr"[#&]subdirectory={parsed.subdirectory}$", "", formatted
            )

        altered = parsed.format() != formatted

        if altered:
            if re.match(r"^git\+https?", url) and re.match(
                r"^/?:[^0-9]", parsed.pathname or ""
            ):
                normalized = re.sub(r"git\+(.*:[^:]+):(.*)", "\\1/\\2", url)
            elif re.match(r"^git\+file", url):
                normalized = re.sub(r"git\+", "", url)
            else:
                normalized = re.sub(r"^(?:git\+)?ssh://", "", url)
        else:
            normalized = parsed.format()

        return GitUrl(
            re.sub(r"#[^#]*$", "", normalized), parsed.rev, parsed.subdirectory
        )

    @property
    def config(self) -> GitConfig:
        return self._config

    def clone(self, repository: str, dest: Path) -> str:
        self._check_parameter(repository)

        return self.run("clone", "--recurse-submodules", "--", repository, str(dest))

    def checkout(self, rev: str, folder: Optional[Path] = None) -> str:
        args = []
        if folder is None and self._work_dir:
            folder = self._work_dir

        if folder:
            args += [
                "--git-dir",
                (folder / ".git").as_posix(),
                "--work-tree",
                folder.as_posix(),
            ]

        self._check_parameter(rev)

        args += ["checkout", rev]

        return self.run(*args)

    def rev_parse(self, rev: str, folder: Optional[Path] = None) -> str:
        args = []
        if folder is None and self._work_dir:
            folder = self._work_dir

        self._check_parameter(rev)

        # We need "^0" (an alternative to "^{commit}") to ensure that the
        # commit SHA of the commit the tag points to is returned, even in
        # the case of annotated tags.
        #
        # We deliberately avoid the "^{commit}" syntax itself as on some
        # platforms (cygwin/msys to be specific), the braces are interpreted
        # as special characters and would require escaping, while on others
        # they should not be escaped.
        args += ["rev-parse", rev + "^0"]

        return self.run(*args, folder=folder)

    def get_current_branch(self, folder: Optional[Path] = None) -> str:
        if folder is None and self._work_dir:
            folder = self._work_dir

        output = self.run("symbolic-ref", "--short", "HEAD", folder=folder)

        return output.strip()

    def get_ignored_files(self, folder: Optional[Path] = None) -> list:
        args = []
        if folder is None and self._work_dir:
            folder = self._work_dir

        if folder:
            args += [
                "--git-dir",
                (folder / ".git").as_posix(),
                "--work-tree",
                folder.as_posix(),
            ]

        args += ["ls-files", "--others", "-i", "--exclude-standard"]
        output = self.run(*args)

        return output.strip().split("\n")

    def remote_urls(self, folder: Optional[Path] = None) -> dict:
        output = self.run(
            "config", "--get-regexp", r"remote\..*\.url", folder=folder
        ).strip()

        urls = {}
        for url in output.splitlines():
            name, url = url.split(" ", 1)
            urls[name.strip()] = url.strip()

        return urls

    def remote_url(self, folder: Optional[Path] = None) -> str:
        urls = self.remote_urls(folder=folder)

        return urls.get("remote.origin.url", urls[list(urls.keys())[0]])

    def run(self, *args: Any, **kwargs: Any) -> str:
        folder = kwargs.pop("folder", None)
        if folder:
            args = (
                "--git-dir",
                (folder / ".git").as_posix(),
                "--work-tree",
                folder.as_posix(),
            ) + args

        return (
            subprocess.check_output(
                [executable()] + list(args), stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )

    def _check_parameter(self, parameter: str) -> None:
        """
        Checks a git parameter to avoid unwanted code execution.
        """
        if parameter.strip().startswith("-"):
            raise GitError(f"Invalid Git parameter: {parameter}")