import logging
import os
from pathlib import Path
from typing import Iterable, List, Optional, Pattern

import sentry_sdk

from codecov_cli.helpers.folder_searcher import globs_to_regex, search_files
from codecov_cli.helpers.upload_type import ReportType
from codecov_cli.types import UploadCollectionResultFile

logger = logging.getLogger("codecovcli")


coverage_files_patterns = [
    "*.clover",
    "*.codecov.*",
    "*.gcov",
    "*.lcov",
    "*.lst",
    "*coverage*.*",
    "*Jacoco*.xml",
    "clover.xml",
    "cobertura.xml",
    "codecov-result.json",
    "codecov.*",
    "cover.out",
    "coverage-final.json",
    "excoveralls.json",
    "gcov.info",
    "jacoco*.xml",
    "lcov.dat",
    "pylcov.dat",
    "lcov.info",
    "luacov.report.out",
    "naxsi.info",
    "nosetests.xml",
    "report*.xml",
    "test_cov.xml",
]

test_results_files_patterns = [
    "*junit*.xml",
    "*test*.xml",
    # the actual JUnit (Java) prefixes the tests with "TEST-"
    "*TEST-*.xml",
]

coverage_files_excluded_patterns = [
    "*.*js",
    "*.SHA256SUM",
    "*.am",
    "*.bash",
    "*.bat",
    "*.bw",
    "*.cfg",
    "*.class",
    "*.cmake",
    "*.conf",
    "*.coverage",
    "*.cp",
    "*.cpp",
    "*.crt",
    "*.csg",
    "*.css",
    "*.csv",
    "*.dart",
    "*.data",
    "*.db",
    "*.dox",
    "*.ec",
    "*.egg",
    "*.egg-info",
    "*.el",
    "*.env",
    "*.erb",
    "*.err",
    "*.exe",
    "*.feature",
    "*.ftl",
    "*.gif",
    "*.go",
    "*.gradle",
    "*.gz",
    "*.h",
    "*.html",
    "*.in",
    "*.jade",
    "*.jar*",
    "*.jpeg",
    "*.jpg",
    "*.js",
    "*.less",
    "*.library",
    "*.log",
    "*.m4",
    "*.mak*",
    "*.map",
    "*.md",
    "*.module",
    "*.mp4",
    "*.o",
    "*.p12",
    "*.pem",
    "*.png",
    "*.pom*",
    "*.profdata",
    "*.proto",
    "*.prototxt",
    "*.ps1",
    "*.pth",
    "*.py",
    "*.pyc",
    "*.pyo",
    "*.rake",
    "*.rb",
    "*.rsp",
    "*.rst",
    "*.ru",
    "*.sbt",
    "*.scss",
    "*.serialized",
    "*.sh",
    "*.sha256sum",
    "*.snapshot",
    "*.sql",
    "*.svg",
    "*.tar.tz",
    "*.template",
    "*.ts",
    "*.whl",
    "*.xcconfig",
    "*.xcoverage.*",
    "*.yaml",
    "*.yml",
    "*.zip",
    "*/classycle/report.xml",
    "*codecov.yml",
    "*~",
    ".*coveragerc",
    ".coverage*",
    ".ds_store",
    ".git*",
    ".nvmrc",
    "codecov.SHA256SUM",
    "codecov.SHA256SUM.sig",
    "codecov.yaml",
    "coverage-summary.json",
    "createdFiles.lst",
    "fullLocaleNames.lst",
    "include.lst",
    "inputFiles.lst",
    "phpunit-code-coverage.xml",
    "phpunit-coverage.xml",
    "remapInstanbul.coverage*.json",
    "scoverage.measurements.*",
    "test-result-*-codecoverage.json",
    "test_*_coverage.txt",
    "testrunner-coverage*",
]

test_results_files_excluded_patterns = (
    coverage_files_patterns + coverage_files_excluded_patterns
)


default_folders_to_ignore = [
    "vendor",
    "bower_components",
    ".circleci",
    "conftest_*.c.gcov",
    ".egg-info*",
    ".env",
    ".envs",
    ".git",
    ".go",
    ".hg",
    ".map",
    ".marker",
    ".tox",
    ".venv",
    ".venvs",
    ".virtualenv",
    ".virtualenvs",
    ".yarn",
    ".yarn-cache",
    "__pycache__",
    "env",
    "envs",
    "htmlcov",
    "js/generated/coverage",
    "node_modules",
    "venv",
    "venvs",
    "virtualenv",
    "virtualenvs",
    "jspm_packages",
    ".nyc_output",
]


class FileFinder(object):
    def __init__(
        self,
        search_root: Optional[Path] = None,
        folders_to_ignore: Optional[List[Path]] = None,
        explicitly_listed_files: Optional[List[Path]] = None,
        disable_search: bool = False,
        report_type: ReportType = ReportType.COVERAGE,
    ):
        self.search_root = search_root or Path(os.getcwd())
        self.folders_to_ignore = (
            [f.as_posix() for f in folders_to_ignore] if folders_to_ignore else []
        )
        self.explicitly_listed_files = explicitly_listed_files or []
        self.disable_search = disable_search
        self.report_type: ReportType = report_type

    def find_files(self) -> List[UploadCollectionResultFile]:
        with sentry_sdk.start_span(name="find_files"):
            if self.report_type == ReportType.COVERAGE:
                files_excluded_patterns = coverage_files_excluded_patterns
                files_patterns = coverage_files_patterns
            elif self.report_type == ReportType.TEST_RESULTS:
                files_excluded_patterns = test_results_files_excluded_patterns
                files_patterns = test_results_files_patterns
            regex_patterns_to_exclude = globs_to_regex(files_excluded_patterns)
            assert regex_patterns_to_exclude  # this is never `None`
            files_paths: Iterable[Path] = []
            user_files_paths = []
            if self.explicitly_listed_files:
                user_files_paths = self.get_user_specified_files(
                    regex_patterns_to_exclude
                )
            if not self.disable_search:
                regex_patterns_to_include = globs_to_regex(files_patterns)
                assert regex_patterns_to_include  # this is never `None`
                files_paths = search_files(
                    self.search_root,
                    default_folders_to_ignore + self.folders_to_ignore,
                    filename_include_regex=regex_patterns_to_include,
                    filename_exclude_regex=regex_patterns_to_exclude,
                )
            result_files = [UploadCollectionResultFile(path) for path in files_paths]
            user_result_files = [
                UploadCollectionResultFile(path)
                for path in user_files_paths
                if user_files_paths
            ]

            user_result_files = []
            for path in user_files_paths:
                if os.path.isfile(path):
                    user_result_files.append(UploadCollectionResultFile(path))
                else:
                    logger.warning(
                        f'File "{path}" could not be found or does not exist. Please enter in the full path or from the search root "{self.search_root}"',
                    )

            return list(set(result_files + user_result_files))

    def get_user_specified_files(self, regex_patterns_to_exclude: Pattern):
        user_filenames_to_include = []
        files_excluded_but_user_includes = []
        for file in self.explicitly_listed_files:
            user_filenames_to_include.append(file.name)
            if regex_patterns_to_exclude.match(file.name):
                files_excluded_but_user_includes.append(file.as_posix())
        if files_excluded_but_user_includes:
            logger.warning(
                "Some files being explicitly added are found in the list of excluded files for upload. We are still going to search for the explicitly added files.",
                extra=dict(
                    extra_log_attributes=dict(files=files_excluded_but_user_includes)
                ),
            )
        regex_patterns_to_include = globs_to_regex(user_filenames_to_include)
        multipart_include_regex = globs_to_regex(
            [path.resolve().as_posix() for path in self.explicitly_listed_files]
        )
        user_files_paths = list(
            search_files(
                self.search_root,
                self.folders_to_ignore,
                filename_include_regex=regex_patterns_to_include,
                multipart_include_regex=multipart_include_regex,
            )
        )
        not_found_files = []
        user_files_paths_resolved = [path.resolve() for path in user_files_paths]
        for filepath in self.explicitly_listed_files:
            if filepath.resolve() not in user_files_paths_resolved:
                ## The file given might be linked or in a parent dir, check to see if it exists
                if filepath.exists():
                    user_files_paths.append(filepath)
                else:
                    not_found_files.append(filepath)

        if not_found_files:
            logger.warning(
                "Some files were not found",
                extra=dict(extra_log_attributes=dict(not_found_files=not_found_files)),
            )

        return user_files_paths


def select_file_finder(
    root_folder_to_search,
    folders_to_ignore,
    explicitly_listed_files,
    disable_search,
    report_type: ReportType = ReportType.COVERAGE,
):
    return FileFinder(
        root_folder_to_search,
        folders_to_ignore,
        explicitly_listed_files,
        disable_search,
        report_type,
    )
