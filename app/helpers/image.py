from PIL import Image

MAX_IMAGE_SIZE = 300

def resize_image(imageField):
    image = imageField.open(mode="r+")

    width = image.width
    height = image.height

    filename = image.path

    max_size = max(width, height)

    if max_size > MAX_IMAGE_SIZE: 
        image = Image.open(filename)
        image = image.resize(
            (round(width / max_size * MAX_IMAGE_SIZE),
             round(height / max_size * MAX_IMAGE_SIZE)),
            Image.ANTIALIAS
        )
        image.save(filename)