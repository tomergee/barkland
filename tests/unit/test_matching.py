from barkland.engine.matching import match_play_partners

def test_match_play_partners_even_count():
    dogs = ["Buddy", "Stella", "Buster", "Luna"]
    pairs, unmatched = match_play_partners(dogs)
    
    assert len(pairs) == 2
    assert ("Buddy", "Stella") in pairs
    assert ("Buster", "Luna") in pairs
    assert len(unmatched) == 0

def test_match_play_partners_odd_count():
    dogs = ["Buddy", "Stella", "Buster"]
    pairs, unmatched = match_play_partners(dogs)
    
    assert len(pairs) == 1
    assert ("Buddy", "Stella") in pairs
    assert len(unmatched) == 1
    assert "Buster" in unmatched

def test_match_play_partners_empty():
    pairs, unmatched = match_play_partners([])
    assert len(pairs) == 0
    assert len(unmatched) == 0
