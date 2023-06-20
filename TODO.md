# Decorator for now-required methods

Three methods, `lst`, `kill`, and `decel` are "now-required". These methods operate nearly the same on their data would be good to have a decorator like `AllowNow` (abstract `AllowNow` to accept `AllowNow(False)`, or just create an `OnlyNow`?).

# More robust command check helper

eg check if command starts in C and ends in R.

- Could make sure commands aren't too long; pg 16 of guide says each program can be 256 bytes (there are 5 programs)
- "M" requests memory available in current program, could if added commands will fit from that.

# Implement command return checking

Some commands, like `run`, `kill`, and `decelerate` send back a `^` in response (pg 23 in guide, pg 24 states it is sent after program completion and the host should look for it). eg `read_all` will return `^` when the program completes. Somehow the the command itself is buffered (even when echo is off?), read by `read_all`?

# Implement proper user feedback

- U6 causes "W" to be sent to host and waits for "G" to continue (pg 14); example of a raster that uses this on on pg 28

# Implement limit switch read state

- '?' (pg 15)

# Some notes on VMX behavior

Most are in the code itself.

1. Most status commands, like `X` if run in the middle of a program (eg before an R), will cause the VMX to error out.
