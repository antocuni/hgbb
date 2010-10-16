import hgbb
from hgbb import parse_repopath
from mercurial import extensions, commands
from mock import Mock
import getpass


def pytest_funcarg__ui(request):
    return Mock(name='ui')


def pytest_generate_tests(metafunc):
    if 'path' in metafunc.funcargnames:
        for id, path, expected_name in parse_repopath_cases:
            metafunc.addcall(id=id,
                             funcargs={
                                 'path': path,
                                 'expected_name': expected_name,
                             })


def test_get_username(monkeypatch, ui):
    getuser = Mock(return_value='fromgetpass')
    monkeypatch.setattr(getpass, 'getuser',  getuser)

    ui.config.return_value = 'fromconfig'
    assert hgbb.get_username(ui) == 'fromconfig'

    ui.reset_mock()
    ui.config.return_value = None
    assert hgbb.get_username(ui) == 'fromgetpass'


parse_repopath_cases = [
    # some valid cases
    ('bb http url', 'http://bitbucket.org/the/repo', 'the/repo'),
    ('bb ssh url', 'ssh://bitbucket.org/the/repo', 'the/repo'),
    ('bb colon', 'bb:test', 'test'),
    ('bb plus colon', 'bb+something:test', 'test'),  # kinda evil
    # some invalid cases
    ('stray bb prefix', 'bbfoo', None),
    ('stray bb plus prefix', 'bb+foo', None),
    ('some name', 'some/name', None),
]


def test_parse_repopath(path, expected_name):
    reponame = parse_repopath(path)
    assert reponame == expected_name


def test_get_reponame(monkeypatch, ui):
    monkeypatch.setattr(hgbb, 'get_username', Mock(return_value='test'))
    monkeypatch.setattr(hgbb, 'parse_repopath', Mock(return_value='test/path'))
    repo = Mock()
    repo.root = 'the/basename'
    # guessed from repo root
    ui.configitems.return_value = []
    name = hgbb.get_bbreponame(ui, repo, {})
    assert name == 'test/basename'
    assert ui.status.called  # warned cause of construction

    ui.reset_mock()
    # grab from url
    ui.configitems.return_value = [('default', None)]
    name = hgbb.get_bbreponame(ui, repo, {})
    assert name == 'test/path'
    assert ui.status.called

    ui.reset_mock()
    # given short name
    name = hgbb.get_bbreponame(ui, repo, {'reponame': 'given'})
    assert name == 'test/given'
    assert ui.status.called

    ui.reset_mock()
    # given full name
    name = hgbb.get_bbreponame(ui, repo, {'reponame': 'full/given'})
    assert name == 'full/given'
    assert not ui.status.called


def test_clone_wrapper_path_mapping(ui):
    mock = Mock()
    hgbb.clone(mock, ui, 'bb:test')
    #                       ui,   source,      dest
    mock.assert_called_with(ui, 'bb://test', None)

    mock.reset_mock()
    hgbb.clone(mock, ui, 'bb://test')
    #                       ui,   source,      dest
    mock.assert_called_with(ui, 'bb://test', None)


def test_uisetup(monkeypatch, ui):
    mock = Mock()
    monkeypatch.setattr(extensions, 'wrapcommand', mock)
    hgbb.uisetup(ui)
    mock.assert_called_with(commands.table, 'clone', hgbb.clone)
