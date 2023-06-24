# More robust command check helper

eg check if command starts in C and ends in R.

- Could make sure commands aren't too long; pg 16 of guide says each program can be 256 bytes (there are 5 programs)
- "M" requests memory available in current program, could if added commands will fit from that.

# Better command return checking

Some commands, such as `run`, `kill`, and `decelerate`, send back a `^` in response (pg 23 in guide, pg 24 states it is sent after program completion and the host should look for it).

We have a basic "wait_for_complete", but there could be a way to handle it better.

# Implement proper user feedback

- U6 causes "W" to be sent to host and waits for "G" to continue (pg 14); example of a raster that uses this on on pg 28

# Implement limit switch read state

- '?' (pg 15)

# Some notes on VMX behavior

Most are in the code itself.

# Second startup fails

Starting a VMX instance a second time errors out. For some reason the `res` causes the VMX to enter a bad state (ie return `B` and flash the on-line orange LED).

1. Most status commands, like `X` if run in the middle of a program (eg before an R), will cause the VMX to error out.
