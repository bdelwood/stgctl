# Usage

```{eval-rst}
.. cyclopts:: stgctl.cli:cli
   :heading-level: 2
   :max-heading-level: 2
```

## Raster modes

Run a standard (step and wait) raster with `stgctl stages run raster`. 

Run a continuous raster with `stgctl stages run continuous-raster`. The stage
uses the configured grid geometry, scans each row without stopping at
intermediate X points, and keeps acquisition active across the full raster. Set
`STGCTL_CONTINUOUS_RASTER_SPEED` to control the motor speed; the default is 800
idx/s.

Preview either mode with `stgctl stages run raster --dry-run` or
`stgctl stages run continuous-raster --dry-run`. Dry-run mode initializes
neither the VMX controller nor SSH signaling and uses simulated travel of 10,000
indexes in both X and Y. Configure the preview grid with `STGCTL_GRID_SIZE`, for
example `STGCTL_GRID_SIZE='[10,10]'`.
