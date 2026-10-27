"""Settings you can change without touching the rest of the code."""

# Which pair of stations is yours:
#   "fulton"          = Franklin Av (C + shuttle) and Nostrand Av (A, C) on Fulton St
#   "eastern_parkway" = Franklin Av (2, 3, 4, 5) and Nostrand Av (3) on Eastern Parkway
CORRIDOR = "fulton"

# What "Alexa, open train times" reads out when you don't name a direction.
#   "N" = Manhattan-bound only, "S" = Brooklyn-bound only, None = both
DEFAULT_DIRECTION = "N"

# Which stations the opening summary covers, in order.
DEFAULT_STATIONS = ["franklin", "nostrand"]

# How many upcoming trains to read per direction.
TRAINS_TO_READ = 3
