def post_process_classify(classes: dict) -> dict:
    pp_classes = []
    for key, value in classes.items():
        if value:
            pp_classes.append(key)
    return pp_classes