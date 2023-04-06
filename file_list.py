import os

# directory_path = "/Users/gregoryfinley/Dropbox"
directory_path = (
    "/Users/gregoryfinley/Dropbox/Greg Stuff/Greg Documents/CHICO STATE/Soph"
)


def build_file_list(directory_path):
    file_list = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            file_list.extend(build_file_list(file_path))
        else:
            file_list.append(file_path)

    return file_list


file_list = build_file_list(directory_path)
with open("file_list.txt", "w") as file:
    for file_path in file_list:
        file.write(file_path + "\n")
