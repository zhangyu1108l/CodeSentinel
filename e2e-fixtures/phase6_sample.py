def average(values):
    return sum(values) / len(values)


def safe_average(values):
    if not values:
        return 0.0
    return sum(values) / len(values)
