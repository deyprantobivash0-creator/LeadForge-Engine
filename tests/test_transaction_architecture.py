"""Small deterministic runtime ownership inventory; not whole-Python analysis."""

import ast
from pathlib import Path, PurePosixPath

import pytest


INFRASTRUCTURE = {
    "backend/database/transactions.py": {"service_transaction", "rollback_safely"},
    "backend/database/transaction_policy.py": {"start", "bind", "check", "consume", "after_begin", "ensure_physical", "commit", "rollback", "service_savepoint"},
}
QUARANTINED = {
    "backend/core/organization.py", "backend/database/init_db.py",
    "backend/ingestion/ingestion_service.py",
}
FORBIDDEN_MODULES = {
    "backend.core.organization", "backend.database.init_db", "backend.ingestion.ingestion_service",
}
CONTROL = {"commit", "rollback", "begin", "begin_nested", "exec_driver_sql", "raw_connection", "cursor", "connection"}
RAW = {"driver_connection", "dbapi_connection"}
MODES = {"autocommit", "isolation_level"}
DDL_MODULES = {"sqlalchemy", "sqlalchemy.schema", "sqlalchemy.sql.ddl", "sqlalchemy.sql.expression"}
DDL_CONSTRUCTORS = {
    "DDL", "DDLElement", "ExecutableDDLElement", "AddConstraint", "DropConstraint",
    "CreateTable", "DropTable", "CreateIndex", "DropIndex", "CreateSchema", "DropSchema",
    "CreateSequence", "DropSequence", "SetTableComment", "DropTableComment",
    "SetColumnComment", "DropColumnComment", "SetConstraintComment", "DropConstraintComment",
}


def module_and_package(path):
    path = PurePosixPath(str(path).replace("\\", "/"))
    parts = path.with_suffix("").parts
    is_package = parts[-1] == "__init__"
    module = ".".join(parts[:-1] if is_package else parts)
    package = module if is_package else ".".join(parts[:-1])
    return module, package


def resolve_import_from(path, level, module):
    if level == 0:
        return module or ""
    _, package = module_and_package(path)
    parts = package.split(".") if package else []
    if level < 1 or level > len(parts):
        return None
    parent = parts[:len(parts) - level + 1]
    return ".".join(parent + (module.split(".") if module else []))


def violations(source, path):
    path = PurePosixPath(str(path).replace("\\", "/")).as_posix()
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    def owner(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None
    result = set()
    aliases = {}
    sqlalchemy_aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = resolve_import_from(path, node.level, node.module)
            if module is None:
                target = "." * node.level + (node.module or "")
                result.add((path, node.lineno, "TX-IMPORT", target))
                continue
            if module in FORBIDDEN_MODULES or module.startswith("backend.script"):
                result.add((path, node.lineno, "TX-QUARANTINE", module))
            for name in node.names:
                aliases[name.asname or name.name] = name.name
                if module in DDL_MODULES or module == "sqlalchemy.sql":
                    sqlalchemy_aliases[name.asname or name.name] = module + "." + name.name
                full_module = module + "." + name.name
                if full_module in FORBIDDEN_MODULES or full_module.startswith("backend.script"):
                    result.add((path, node.lineno, "TX-QUARANTINE", full_module))
                if full_module in {"backend.database.transactions", "backend.database.transaction_policy"} and path not in INFRASTRUCTURE:
                    result.add((path, node.lineno, "TX-AUTHORITY", full_module))
                if (module == "backend.database.transaction_policy" and path not in INFRASTRUCTURE
                        and name.name not in {"require_governed_physical_root", "TransactionPolicyViolation"}):
                    result.add((path, node.lineno, "TX-AUTHORITY", name.name))
                if (module == "backend.database.transactions" and path not in INFRASTRUCTURE
                        and name.name not in {"service_transaction", "service_savepoint", "in_service_transaction", "TransactionAborted"}):
                    result.add((path, node.lineno, "TX-AUTHORITY", name.name))
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name == "sqlalchemy" or name.name.startswith("sqlalchemy."):
                    sqlalchemy_aliases[name.asname or "sqlalchemy"] = name.name if name.asname else "sqlalchemy"
                if name.name in FORBIDDEN_MODULES or name.name.startswith("backend.script"):
                    result.add((path, node.lineno, "TX-QUARANTINE", name.name))
                if name.name in {"backend.database.transactions", "backend.database.transaction_policy"} and path not in INFRASTRUCTURE:
                    result.add((path, node.lineno, "TX-AUTHORITY", name.name))
    for node in ast.walk(tree):
        if owner(node) in INFRASTRUCTURE.get(path, set()):
            continue
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            resolved = aliases.get(name, name)
            parts, function = [], node.func
            while isinstance(function, ast.Attribute):
                parts.insert(0, function.attr)
                function = function.value
            if isinstance(function, ast.Name):
                target = ".".join([sqlalchemy_aliases.get(function.id, function.id), *parts])
                module, _, symbol = target.rpartition(".")
                if module in DDL_MODULES and symbol in DDL_CONSTRUCTORS:
                    result.add((path, node.lineno, "TX-DDL", target))
            if name in CONTROL:
                result.add((path, node.lineno, "TX-CONTROL", name))
            factory_allowed = (
                (path == "backend/database/session.py" and owner(node) is None and resolved in {"create_engine", "sessionmaker"})
                or (path == "backend/database/dependencies.py" and owner(node) == "get_db" and resolved == "SessionLocal")
                or (path == "backend/repositories/runtime_readiness_repository.py" and owner(node) == "migration_heads" and resolved == "SessionLocal"))
            if resolved in {"create_engine", "sessionmaker", "Session", "SessionLocal"} and not factory_allowed:
                result.add((path, node.lineno, "TX-FACTORY", resolved))
            if resolved in {"text", "literal_column"}:
                # Model metadata defaults are schema declarations, not opaque execution.
                parent = parents.get(node)
                default = (path.startswith("backend/models/") and isinstance(parent, ast.keyword)
                           and parent.arg == "server_default" and resolved == "text"
                           and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
                           and node.args[0].value in {"true", "CURRENT_TIMESTAMP"})
                readiness = (path == "backend/repositories/runtime_readiness_repository.py"
                             and owner(node) == "migration_heads" and len(node.args) == 1
                             and isinstance(node.args[0], ast.Constant)
                             and node.args[0].value in {"SELECT 1", "SELECT version_num FROM alembic_version"})
                if not default and not readiness:
                    result.add((path, node.lineno, "TX-OPAQUE", resolved))
            if name == "execution_options" and any(k.arg in MODES for k in node.keywords):
                result.add((path, node.lineno, "TX-MODE", name))
        if isinstance(node, ast.Attribute) and node.attr in RAW:
            result.add((path, node.lineno, "TX-RAW", node.attr))
        if isinstance(node, ast.Attribute) and node.attr in CONTROL:
            result.add((path, node.lineno, "TX-CONTROL", node.attr))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in MODES:
                    result.add((path, node.lineno, "TX-MODE", target.attr))
    return sorted(result)


def test_runtime_transaction_inventory():
    root = Path(__file__).resolve().parents[1]
    findings = []
    for file in sorted((root / "backend").rglob("*.py")):
        path = file.relative_to(root).as_posix()
        if path in QUARANTINED or path.startswith("backend/script/"):
            continue
        findings.extend(violations(file.read_text(encoding="utf-8-sig"), path))
    assert findings == []


@pytest.mark.parametrize("source,rule", [
    ("db.commit()", "TX-CONTROL"), ("session.rollback()", "TX-CONTROL"),
    ("conn.commit()", "TX-CONTROL"), ("connection.rollback()", "TX-CONTROL"),
    ("db.begin_nested()", "TX-CONTROL"), ('conn.exec_driver_sql("COMMIT")', "TX-CONTROL"),
    ("engine.raw_connection()", "TX-CONTROL"), ("driver.cursor()", "TX-CONTROL"),
    ("conn.connection.driver_connection", "TX-RAW"), ("driver.autocommit = True", "TX-MODE"),
    ('conn.execution_options(isolation_level="AUTOCOMMIT")', "TX-MODE"),
    ('from sqlalchemy import create_engine as make\nmake("unused")', "TX-FACTORY"),
    ('from sqlalchemy import text as raw\nraw("COMMIT")', "TX-OPAQUE"),
    ("from backend.core.organization import get_or_create_default_organization as implicit", "TX-QUARANTINE"),
    ("settle = db.commit\nsettle()", "TX-CONTROL"),
    ("from backend.database.transaction_policy import current_root as authority", "TX-AUTHORITY"),
    ("from backend.database import init_db", "TX-QUARANTINE"),
    ("from backend.database.transactions import current_root", "TX-AUTHORITY"),
])
def test_synthetic_violations(source, rule):
    found = violations(source, "backend/services/synthetic.py")
    assert any(item[2] == rule for item in found)
    assert found == sorted(found)


def test_harmless_bound_sql():
    assert violations("db.execute(select(Lead).where(Lead.id == target))", "backend/services/synthetic.py") == []


@pytest.mark.parametrize("path,module,package", [
    ("backend/services/foo.py", "backend.services.foo", "backend.services"),
    ("backend/database/transaction_policy.py", "backend.database.transaction_policy", "backend.database"),
    ("backend/__init__.py", "backend", "backend"),
    ("backend/services/__init__.py", "backend.services", "backend.services"),
    (r"backend\services\foo.py", "backend.services.foo", "backend.services"),
    (r"backend\services\__init__.py", "backend.services", "backend.services"),
    ("standalone.py", "standalone", ""),
])
def test_module_package_derivation(path, module, package):
    assert module_and_package(path) == (module, package)


@pytest.mark.parametrize("path,level,module,target", [
    ("backend/services/foo.py", 0, "backend.models.lead", "backend.models.lead"),
    ("backend/services/foo.py", 1, "analysis_service", "backend.services.analysis_service"),
    ("backend/services/foo.py", 2, "core.organization", "backend.core.organization"),
    ("backend/services/foo.py", 2, None, "backend"),
    ("backend/api/routes/foo.py", 3, "core.organization", "backend.core.organization"),
    ("backend/services/__init__.py", 1, "analysis_service", "backend.services.analysis_service"),
    ("backend/services/__init__.py", 2, "core", "backend.core"),
    ("backend/__init__.py", 1, "models", "backend.models"),
    ("standalone.py", 1, "models", None),
    ("backend/services/foo.py", 3, "something", None),
    ("backend/__init__.py", 2, "something", None),
    (r"backend\services\foo.py", 2, "models.lead", "backend.models.lead"),
])
def test_import_from_levels(path, level, module, target):
    assert resolve_import_from(path, level, module) == target


@pytest.mark.parametrize("module,symbol", [
    ("core.organization", "get_or_create_default_organization"),
    ("database.init_db", "init_db"),
    ("ingestion.ingestion_service", "IngestionService"),
    ("script.migrate_performance_indexes", "main"),
])
def test_relative_quarantine_matches_absolute(module, symbol):
    path = "backend/services/example_service.py"
    expected = [(path, 1, "TX-QUARANTINE", "backend." + module)]
    if module.startswith("script."):
        expected.append((path, 1, "TX-QUARANTINE", "backend." + module + "." + symbol))
    for source in (
        f"from backend.{module} import {symbol}",
        f"from ..{module} import {symbol}",
        f"from ..{module} import {symbol} as helper\nhelper(db)",
    ):
        assert violations(source, path) == expected


@pytest.mark.parametrize("module,symbol,rule", [
    ("core", "organization", "TX-QUARANTINE"),
    ("database", "init_db", "TX-QUARANTINE"),
    ("ingestion", "ingestion_service", "TX-QUARANTINE"),
    ("database", "transaction_policy", "TX-AUTHORITY"),
    ("database", "transactions", "TX-AUTHORITY"),
    ("", "script", "TX-QUARANTINE"),
])
def test_relative_package_import_matches_absolute(module, symbol, rule):
    path = "backend/services/example_service.py"
    absolute = "backend" + ("." + module if module else "")
    relative = ".." + module
    expected = [(path, 1, rule, absolute + "." + symbol)]
    assert violations(f"from {absolute} import {symbol} as target", path) == expected
    assert violations(f"from {relative} import {symbol} as target", path) == expected


PRIVATE_POLICY_SYMBOLS = (
    "_restricted_sql_commands",
    "Operation", "RootAuthority", "_Permit", "_permit", "_flushing", "_roots",
    "_MISSING", "current_root", "GovernedRoot", "service_savepoint",
)


@pytest.mark.parametrize("symbol", PRIVATE_POLICY_SYMBOLS)
def test_relative_private_authority_matches_absolute(symbol):
    path = "backend/services/example_service.py"
    expected = [(path, 1, "TX-AUTHORITY", symbol)]
    for source in (
        f"from backend.database.transaction_policy import {symbol}",
        f"from ..database.transaction_policy import {symbol}",
        f"from ..database.transaction_policy import {symbol} as root_state",
    ):
        assert violations(source, path) == expected


def test_private_policy_symbol_inventory():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "backend/database/transaction_policy.py").read_text(encoding="utf-8-sig"))
    declared = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            declared.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            declared.update(target.id for target in targets if isinstance(target, ast.Name))
    assert declared - {"require_governed_physical_root", "TransactionPolicyViolation"} == set(PRIVATE_POLICY_SYMBOLS)


@pytest.mark.parametrize("source,rule,target", [
    ("import backend.core.organization as helper", "TX-QUARANTINE", "backend.core.organization"),
    ("import backend.database.transaction_policy as policy", "TX-AUTHORITY", "backend.database.transaction_policy"),
    ("import backend.script.migrate_performance_indexes", "TX-QUARANTINE", "backend.script.migrate_performance_indexes"),
])
def test_absolute_import_statement_unchanged(source, rule, target):
    path = "backend/services/example_service.py"
    assert violations(source, path) == [(path, 1, rule, target)]


@pytest.mark.parametrize("source", [
    "from backend.models.lead import Lead",
    "from ..models.lead import Lead",
    "from .analysis_service import AnalysisService",
    "from .. import core",
    "from ..database.transaction_policy import require_governed_physical_root",
    "from ..database.transaction_policy import TransactionPolicyViolation",
    "from ..database.transactions import service_transaction, service_savepoint, in_service_transaction, TransactionAborted",
])
def test_benign_absolute_and_relative_imports(source):
    assert violations(source, "backend/services/example_service.py") == []


@pytest.mark.parametrize("path,source", [
    ("backend/__init__.py", "from .core import organization"),
    ("backend/services/__init__.py", "from ..core import organization"),
])
def test_package_initializer_import_policy(path, source):
    assert violations(source, path) == [(path, 1, "TX-QUARANTINE", "backend.core.organization")]


@pytest.mark.parametrize("path,symbol,rule", [
    ("backend/core/example.py", "organization", "TX-QUARANTINE"),
    ("backend/database/example.py", "init_db", "TX-QUARANTINE"),
    ("backend/database/example.py", "transaction_policy", "TX-AUTHORITY"),
])
def test_module_none_relative_import(path, symbol, rule):
    package = module_and_package(path)[1]
    assert violations(f"from . import {symbol}", path) == [(path, 1, rule, package + "." + symbol)]


@pytest.mark.parametrize("source,target", [
    ("from ...core import organization", "...core"),
    ("from .... import database", "...."),
])
def test_invalid_relative_import_fails_closed(source, target):
    path = "backend/services/example_service.py"
    assert violations(source, path) == [(path, 1, "TX-IMPORT", target)]


def test_relative_alias_still_feeds_factory_detection():
    path = "backend/services/example_service.py"
    expected = [(path, 2, "TX-FACTORY", "SessionLocal")]
    for module in ("backend.database.session", "..database.session"):
        assert violations(f"from {module} import SessionLocal as open_db\nopen_db()", path) == expected


def test_relative_findings_are_deterministic_across_path_styles():
    source = "from ..database.transaction_policy import current_root\nfrom ..core import organization"
    findings = violations(source, "backend/services/example_service.py")
    assert findings == sorted(findings)
    assert findings == violations(source, "backend/services/example_service.py")
    assert findings == violations(source, r"backend\services\example_service.py")


def test_resolution_never_imports_or_executes_targets(monkeypatch):
    import builtins
    import importlib
    import sys

    original_import = builtins.__import__
    before = {name for name in sys.modules if name.startswith("backend")}
    def import_tripwire(name, *args, **kwargs):
        if name.startswith("backend") or kwargs.get("level", 0):
            pytest.fail("Static scanner imported runtime code")
        return original_import(name, *args, **kwargs)
    def load_tripwire(*args, **kwargs):
        pytest.fail("Static scanner attempted module loading")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", import_tripwire)
        patch.setattr(importlib, "import_module", load_tripwire)
        source = "from ..core import organization\nraise RuntimeError('Source execution tripwire')"
        assert violations(source, "backend/services/example_service.py") == [
            ("backend/services/example_service.py", 1, "TX-QUARANTINE", "backend.core.organization")]
    assert before == {name for name in sys.modules if name.startswith("backend")}


@pytest.mark.parametrize("source,target", [
    ('from sqlalchemy import DDL\nDDL("COMMIT")', "sqlalchemy.DDL"),
    ('from sqlalchemy import DDL as SQLDDL\nSQLDDL("COMMIT")', "sqlalchemy.DDL"),
    ('import sqlalchemy\nsqlalchemy.DDL("COMMIT")', "sqlalchemy.DDL"),
    ('import sqlalchemy as sa\nsa.DDL("COMMIT")', "sqlalchemy.DDL"),
    ('from sqlalchemy.schema import DDL\nDDL("COMMIT")', "sqlalchemy.schema.DDL"),
    ('import sqlalchemy.schema as schema\nschema.DDL("COMMIT")', "sqlalchemy.schema.DDL"),
    ('from sqlalchemy import schema as s\ns.DDL("COMMIT")', "sqlalchemy.schema.DDL"),
    ('from sqlalchemy.sql import ddl as d\nd.DDL("COMMIT")', "sqlalchemy.sql.ddl.DDL"),
    ('from sqlalchemy.sql.ddl import DDL as MakeDDL\nstmt = MakeDDL("COMMIT")\ndb.execute(stmt)', "sqlalchemy.sql.ddl.DDL"),
    ('import sqlalchemy.sql.ddl\nsqlalchemy.sql.ddl.DDL("COMMIT")', "sqlalchemy.sql.ddl.DDL"),
])
def test_r3a_ddl_alias_and_namespace_forms(source, target):
    path = "backend/services/probe.py"
    assert violations(source, path) == [(path, 2, "TX-DDL", target)]
    assert violations(source, path) == violations(source, r"backend\services\probe.py")


@pytest.mark.parametrize("symbol", sorted(DDL_CONSTRUCTORS))
def test_r3a_public_schema_ddl_construction(symbol):
    source = f"from sqlalchemy.schema import {symbol} as Build\nstmt = Build(argument)\ndb.execute(stmt)"
    assert violations(source, "backend/repositories/probe.py") == [
        ("backend/repositories/probe.py", 2, "TX-DDL", "sqlalchemy.schema." + symbol),
    ]


def test_r3a_public_ddl_inventory():
    from sqlalchemy import schema

    public = {name for name, value in vars(schema).items()
              if not name.startswith("_") and isinstance(value, type)
              and issubclass(value, schema.ExecutableDDLElement)}
    assert DDL_CONSTRUCTORS == public


@pytest.mark.parametrize("source", [
    "from sqlalchemy import select, update, insert, delete, func\nselect(func.count())\nupdate(Lead)\ninsert(Lead)\ndelete(Lead)",
    "import sqlalchemy as sa\nsa.select(Lead)\nsa.func.count()",
    "from sqlalchemy import Table, Column, Integer, MetaData\nTable('example', MetaData(), Column('id', Integer))",
    "from sqlalchemy.schema import Table, Column\nTable(name, metadata, Column(name, datatype))",
])
def test_r3a_benign_sqlalchemy_construction(source):
    assert violations(source, "backend/services/probe.py") == []


@pytest.mark.parametrize("symbol", ["text", "literal_column"])
def test_r3a_existing_opaque_rule_unchanged(symbol):
    source = f'from sqlalchemy import {symbol} as raw\nraw("COMMIT")'
    assert violations(source, "backend/services/probe.py") == [
        ("backend/services/probe.py", 2, "TX-OPAQUE", symbol),
    ]
