def match_play_partners(dogs: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Match dogs in play pairs based on FIFO order.
    Returns:
        pairs: A list of tuples (dog1, dog2) representing matched pairs.
        unmatched: A list of dogs that were not matched.
    """
    pairs = []
    unmatched = []
    for i in range(0, len(dogs), 2):
        if i + 1 < len(dogs):
            pairs.append((dogs[i], dogs[i+1]))
        else:
            unmatched.append(dogs[i])
    return pairs, unmatched
