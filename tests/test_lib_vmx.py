"""Tests for VMX lib"""
from unittest.mock import MagicMock, patch

import pytest
from serial import Serial
from serial.tools.list_ports_common import ListPortInfo
from stgctl.lib.vmx import VMX


@pytest.fixture()
def mock_serial(mocker):
    # Create and return mock serial connection
    mock_serial = MagicMock(spec=Serial)
    mock_serial.write.return_value = None
    mock_serial.readall.return_value = b"R"
    mock_serial.port.return_value = "Test Serial Device"
    mocker.patch("serial.Serial", return_value=mock_serial)
    return mock_serial


@pytest.fixture(autouse=True)
def patched_list_ports_grep():
    mock_port_info = ListPortInfo(device="Test Serial Device")
    with patch("stgctl.lib.vmx.grep_serial_ports", return_value=[mock_port_info]):
        yield


@pytest.fixture
def vmx(mock_serial, monkeypatch):
    mock_serial.readall.return_value = b"R"
    port = None
    with patch("stgctl.lib.vmx.serial.Serial", return_value=mock_serial):
        vmx = VMX(port=port)
    mock_serial.write.reset_mock()
    return vmx


def test_vmx_class_with_patched_grep_serial_ports(patched_list_ports_grep, mock_serial):
    vmx = VMX(port=None)
    assert vmx._serial.port() == "Test Serial Device"


def test_isready_when_not_ready(vmx, mock_serial):
    # Configure the mock serial connection to return something other than "R" when verify is called
    mock_serial.readall.return_value = b""

    # Call the isready method and assert that it returns False
    assert vmx.isready() is False


# Define a list of method names and their expected arguments
method_args_allow_chain = [
    ("run", b"R"),
    ("clear", b"C"),
    ("origin", b"N"),
]

method_args_immediate = [
    ("verify", b"V"),
    ("kill", b"K"),
    ("decel", b"D"),
    ("reset", b"res"),
    ("record_posn", b"!"),
    ("posn", b"X"),
    ("posn", b"Y"),
    ("lst", b"lst"),
]


@pytest.mark.parametrize(
    "method_name, expected_args", method_args_allow_chain + method_args_immediate
)
def test_vmx_methods(vmx, mock_serial, method_name, expected_args):
    # Retrieve the method dynamically based on the name
    method = getattr(vmx, method_name)

    # Call method with now and perform assertions
    method()
    if method_name in method_args_allow_chain:
        assert str(vmx.command_que) == expected_args.decode()
        mock_serial.write.assert_not_called()
    if method_name in method_args_immediate:
        mock_serial.write.assert_called_once()
        assert mock_serial.write.return_value == expected_args


@pytest.mark.parametrize("method_name, expected_args", method_args_allow_chain)
def test_vmx_methods_with_now(vmx, mock_serial, method_name, expected_args):
    # Retrieve the method dynamically based on the name
    method = getattr(vmx, method_name)

    # Call the method without now and perform assertions
    method(now=True)
    mock_serial.write.assert_called_once_with(expected_args)


def test_echo_with_echo_state_true(vmx, mock_serial):
    # Call the echo method with echo_state=True
    vmx.echo(echo_state=True)

    # Verify that the write method of the mock serial connection is called with the expected command
    mock_serial.write.assert_called_once_with(b"F")


def test_echo_with_echo_state_false(vmx, mock_serial):
    # Call the echo method with echo_state=False
    vmx.echo(echo_state=False)

    # Verify that the write method of the mock serial connection is called with the expected command
    mock_serial.write.assert_called_once_with(b"E")


def test_move_relative(vmx, mock_serial):
    # Call the move method with relative=True
    vmx.move(now=True, idx=100, motor=1, relative=True)

    # Verify that the write method of the mock serial connection is called with the expected command
    mock_serial.write.assert_called_once_with(b"I1M100")


def test_move_absolute(vmx, mock_serial):
    # Call the move method with relative=False
    vmx.move(now=True, idx=100, motor=1, relative=False)

    # Verify that the write method of the mock serial connection is called with the expected command
    mock_serial.write.assert_called_once_with(b"IA1M100")


def test_to_limit_positive(vmx, mock_serial):
    mock_serial.readall.return_value = b""
    # Call the to_limit method with pos=True
    vmx.to_limit(now=True, motor=1, pos=True)
    # Verify that the write method of the mock serial connection is called with the expected command
    mock_serial.write.assert_called_once_with(b"I1M0")
