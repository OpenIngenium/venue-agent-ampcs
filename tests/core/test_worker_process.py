import pytest
from unittest.mock import MagicMock, patch

import core.worker_process as wp


@pytest.fixture
def mock_pool():
    fut = MagicMock()
    fut.result.return_value = 1234
    executor = MagicMock()
    executor.submit.return_value = fut
    with patch('core.worker_process.ProcessPoolExecutor', return_value=executor) as ex, \
         patch('core.worker_process.psutil') as ps, \
         patch('core.worker_process.os') as os, \
         patch('core.worker_process.time') as t:
        t.sleep = MagicMock()
        t.time.return_value = 0
        yield ex, executor, ps, os, t


def test_init_worker_proc():
    with patch('core.worker_process.signal') as mock_signal, \
         patch('core.worker_process.current_process', return_value=MagicMock(pid=1234)):
        pid = wp.init_worker_proc()
        assert pid == 1234
        mock_signal.set_wakeup_fd.assert_called_once_with(-1)
        mock_signal.signal.assert_any_call(wp.signal.SIGTERM, wp.signal.SIG_DFL)
        mock_signal.signal.assert_any_call(wp.signal.SIGINT, wp.signal.SIG_DFL)


def test_worker_init(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('test-wp')
    assert w.name == 'test-wp'
    assert w.pid == 1234
    ex.assert_called_once_with(max_workers=1)
    executor.submit.assert_called_once_with(wp.init_worker_proc)


def test_submit_func(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('test-wp')
    dummy = MagicMock(return_value=('out', None))
    fut = MagicMock()
    executor.submit.return_value = fut
    future = w.submit_func(dummy, foo='bar')
    assert future is fut
    executor.submit.assert_called_with(dummy, foo='bar')
    fut.add_done_callback.assert_called_once_with(w.done_callback)
    assert w.future is fut


def test_submit_func_busy(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('test-wp')
    w.future = MagicMock()
    w.future.done.return_value = False
    dummy = MagicMock()
    with pytest.raises(Exception, match='Worker is busy.'):
        w.submit_func(dummy)


def test_done_callback():
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    context = w.future
    context.result.return_value = ('output', 'error')
    w.done_callback(context)
    assert w.output == 'output'
    assert w.error == 'error'
    assert w.future is None


def test_done_callback_not_current():
    w = wp.WorkerProcess('wp')
    other = MagicMock()
    other.result.return_value = ('x', 'y')
    w.future = MagicMock()
    w.done_callback(other)
    assert w.output is None
    assert w.error is None
    assert w.future is not None


def test_clear_status():
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.output = 'x'
    w.error = 'y'
    w.clear_status()
    assert w.future is None
    assert w.output is None
    assert w.error is None


def test_is_running_future_none():
    w = wp.WorkerProcess('wp')
    w.future = None
    assert w.is_running() is False


def test_is_running_future_done():
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.future.done.return_value = True
    assert w.is_running() is False


def test_is_running_future_running():
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.future.done.return_value = False
    assert w.is_running() is True


def test_is_running_future_exception():
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.future.done.side_effect = Exception('boom')
    assert w.is_running() is True


def test_wait_for_completion(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.future.done.side_effect = [False, True]
    w.output = 'out'
    w.error = None
    out, err = w.wait_for_completion()
    assert out == 'out'
    assert err is None
    t.sleep.assert_called_with(0.5)


def test_wait_for_completion_timeout(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.future.done.return_value = False
    t.time.side_effect = [0, 10]
    with pytest.raises(TimeoutError):
        w.wait_for_completion(timeout=2)


def test_shutdown(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('wp')
    w.pid = 1234
    ps.Process.return_value.children.return_value = [MagicMock(pid=111), MagicMock(pid=222)]
    ps.pids.return_value = []
    w.shutdown()
    ps.Process.assert_called_once_with(1234)
    ps.pids.assert_called()
    os.kill.assert_any_call(111, wp.signal.SIGKILL)
    os.kill.assert_any_call(222, wp.signal.SIGKILL)
    os.kill.assert_any_call(1234, wp.signal.SIGKILL)


def test_reset(mock_pool):
    ex, executor, ps, os, t = mock_pool
    w = wp.WorkerProcess('wp')
    w.future = MagicMock()
    w.output = 'x'
    w.error = 'y'
    w.shutdown = MagicMock()
    w._init_pool = MagicMock(side_effect=lambda: setattr(w, 'pid', 9999))
    w.reset()
    w.shutdown.assert_called_once()
    w._init_pool.assert_called_once()
    assert w.future is None
    assert w.output is None
    assert w.error is None
    assert w.pid == 9999
