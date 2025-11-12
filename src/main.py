import argparse
import logging
from datetime import datetime
import os

from config import load_config
from params import load_params, select_params, iter_param_requests
from downloader import download_and_process

# === Logger setup ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Download and process ECMWF polytope data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--config", help="Path to config YAML (default: configs/default.yaml)", default=None)
    parser.add_argument("--dates", nargs="+", help="List of dates (YYYYMMDD)", default=None)
    parser.add_argument("--params", nargs="+", help="Parameter names to download", default=None)
    parser.add_argument("--outdir", help="Override output_dir_base", default=None)
    parser.add_argument("--area", help="Override area", default=None)
    parser.add_argument("--grid", help="Override grid", default=None)
    parser.add_argument("--address", help="Override polytope address", default=None)
    parser.add_argument(
        "--keep-cumulative",
        action="store_true",
        help=(
            "Do NOT convert cumulative variables to interval (hourly) accumulations. "
            "By default, cumulative variables (e.g., precipitation or radiation totals that "
            "accumulate from step 0..N) are converted to per-step intervals using consecutive differences."
        ),
    )

    args = parser.parse_args()

    # === Load config ===
    cfg = load_config(args.config)
    base_request = dict(cfg["base_request"])

    # === Apply overrides ===
    if args.area:
        base_request["area"] = args.area
    if args.grid:
        base_request["grid"] = args.grid

    address = args.address or cfg["address"]
    output_dir_base = args.outdir or cfg["output_dir_base"]

    # === Load and filter parameters ===
    all_params = load_params(cfg["params_file"])
    selected = select_params(all_params, args.params)
    if not selected:
        logger.error("No valid parameters selected. Check your --params list or your params.yaml.")
        raise SystemExit(2)

    # === Dates to process ===
    dates = args.dates or [datetime.utcnow().strftime("%Y%m%d")]

    for date_str in dates:
        logger.info("=" * 60)
        logger.info(f"Processing date: {date_str}")
        logger.info("=" * 60)

        # Build output as data/YYYY/MM/DD
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            logger.error(f"Invalid date format: {date_str}. Expected YYYYMMDD.")
            raise SystemExit(2)

        output_dir = os.path.join(output_dir_base, f"{dt.year:04d}", f"{dt.month:02d}", f"{dt.day:02d}")

        for name, param, request, meta in iter_param_requests(base_request, date_str, selected):
            try:
                var_type = meta.get("type", "instant")
                # Default: convert cumulative→interval unless user keeps cumulative
                convert_cumulative = (var_type == "accum") and (not args.keep_cumulative)
                download_and_process(
                    name=name,
                    request=request,
                    output_dir=output_dir,
                    address=address,
                    var_type=var_type,
                    convert_cumulative=convert_cumulative,
                )
            except Exception as e:
                logger.error(f"Failed to process {name} ({param}) for {date_str}: {e}")
                raise SystemExit(1)

if __name__ == "__main__":
    main()
