"""Keep untrusted strings inert when opened in common spreadsheet programs."""
def spreadsheet_cell(value):
    if isinstance(value, str):
        # Formula prefixes after whitespace/control bytes and leading tab/newline
        # are hazardous in spreadsheet importers, independent of CSV quoting.
        index = 0
        while index < len(value) and (value[index].isspace() or ord(value[index]) < 33):
            index += 1
        significant = value[index:]
        if significant.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
            return "'" + value
    return value
