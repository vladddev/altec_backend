def filtered_menu(menu, allow_pages):
    output_menu = []

    for page in menu:
        if (any(page['link'] in i for i in allow_pages)):
            # output_menu.append(page)
            if 'children' in page:
                page['children'] = filtered_menu(page['children'], allow_pages)
                output_menu.append(page)
            else:
                output_menu.append(page)

    return output_menu


