"""Settings you can change without touching the rest of the code."""

# Which pair of stations is yours (both pairs are in Brooklyn, a mile apart):
#   "franklin_c_nostrand_a" = Franklin Av (C train + shuttle) and Nostrand Av (A and C trains)
#   "eastern_parkway"       = Franklin Av (2, 3, 4, 5) and Nostrand Av (3)
CORRIDOR = "franklin_c_nostrand_a"

# What "Alexa, open train times" reads out when you don't name a direction.
#   "N" = Manhattan-bound only, "S" = Brooklyn-bound only, None = both
DEFAULT_DIRECTION = "N"

# Which stations the opening summary covers, in order.
DEFAULT_STATIONS = ["franklin", "nostrand"]

# How many upcoming trains to read per direction.
TRAINS_TO_READ = 2

# Skip trains you can't catch. A train less than this many minutes away is
# already at the platform or pulling in, so Alexa doesn't mention it. Set it to
# your walking time to the station to only hear trains you can actually make.
# (A "now" train seen live 2026-10-26 was standing at the platform, doors closing.)
HIDE_TRAINS_UNDER_MINUTES = {"franklin": 1, "nostrand": 1}
