from graph.routing import route_chunk,route_document

def test_route_document_final_single_kanji():
    state = {"current_chunk": ["漢"], "has_more": False}
    assert route_document(state) == "select_kanji"

def test_route_document_empty_chunk():
    state = {"current_chunk": [], "has_more": False}
    assert route_document(state) == "finish"

def test_route_document_middle_chunk():
    state = {"current_chunk": ["一"]*15, "has_more": True}
    assert route_document(state) == "select_kanji"

def test_route_chunk_end_of_chunk_with_no_additional_chunks_available():
    state = {"current_chunk":["一","二","三","四"],"current_index":4,"has_more":False}
    assert route_chunk(state) == "finish"

def test_route_chunk_end_of_chunk_with_additional_chunks_available():
    state = {"current_chunk":["一","二","三","四"],"current_index":4,"has_more":True}
    assert route_chunk(state) == "get_next_chunk"

def test_route_chunk_mid_chunk():
    state = {"current_chunk":["一","二","三","四"],"current_index":2,"has_more":False}
    assert route_chunk(state) == "select_kanji"

def test_no_chunk():
    state = {"current_chunk":[],"current_index":0,"has_more":False}
    assert route_chunk(state) == "finish"