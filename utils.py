condition_handler = {
    'bigger': bigger,
    'smaller': smaller,
    'biggerandequal': bigger_equal,
    'smallerandequal': smaller_equal
}


def bigger(data, threshold, avg):
    """
    Check if data > threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data > threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('bigger', 0.5 * (threshold - avg) + avg)
        if data > 0.5 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller(data, threshold, avg):
    """Check if data < threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data < threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smaller', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            print(data, 'yellow')
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color


def bigger_equal(data, threshold, avg):
    """Check if data >= threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data >= threshold:
        triggered = True
        color = 'green'
    else:
        print('biggerequal', 0.78 * (threshold - avg) + avg)
        triggered = False
        if data > 0.78 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller_equal(data, threshold, avg):
    """Check if data <= threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data <= threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smallerequal', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color
