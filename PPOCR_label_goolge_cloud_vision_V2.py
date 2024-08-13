import os
import sys
import argparse
import json
from google.cloud import vision
import yaml
from typing import List, Dict, Any, Tuple


def get_google_ocr_annotation(image_path: str) -> str:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
        "/home/kokupad/paddle/GOOGLE_APPLICATION_CREDENTIALS/voltaic-branch-427005-b3-791c684f135c.json"
    )
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)

    if response.error.message:
        raise Exception(f"{response.error.message}")

    texts = response.text_annotations
    if texts:
        extracted_text = texts[0].description
    else:
        extracted_text = ""

    return extracted_text


def get_image_crop_list(image_name: str, crop_images_list: List[str]) -> List[str]:
    image_name = image_name.split(".")[0]
    crop_image_list = [
        image for image in crop_images_list if image.startswith(image_name)
    ]
    return crop_image_list


def get_crop_image_index(crop_image_name: str) -> int:
    parts = crop_image_name.split("_")
    index = int(parts[-1].split(".")[0])

    return index


def put_txt_to_list(file_path: str) -> List[str]:
    lines_list = []

    with open(file_path, "r") as file:
        lines_list = file.readlines()

    return lines_list


def update_rec_annotation(
    rec_path: str,
    main_image_dict: Dict[str, List[str]],
    annotation_dict: Dict[str, Dict[int, str]],
) -> List[str]:

    rec_list = put_txt_to_list(rec_path)
    # Process each line
    for image_name in main_image_dict.keys():
        crop_image_list = main_image_dict[image_name]
        for crop_image in crop_image_list:

            for i, line in enumerate(rec_list):
                search_quary = "crop_img/" + crop_image
                if line.startswith(search_quary):

                    index = get_crop_image_index(crop_image)

                    annotation = annotation_dict[image_name][index]
                    updated_line = line.split("\t")[0] + "\t" + annotation + "\n"

                    rec_list[i] = updated_line
                    break

    return rec_list


def get_crop_images_annotations(
    boxed_image_dict: Dict[str, List[str]], crop_images_folder_path: str
) -> Dict[str, Dict[int, str]]:
    annotation_dict = {}

    for image_name in boxed_image_dict.keys():
        selected_crop_images_list = boxed_image_dict[image_name]
        annotation_dict[image_name] = {}
        for crop_image in selected_crop_images_list:
            crop_image_path = os.path.join(crop_images_folder_path, crop_image)
            annotation = get_google_ocr_annotation(crop_image_path)
            print(f"{crop_image} -- OCR result is {annotation}")

            index = get_crop_image_index(crop_image)
            annotation_dict[image_name][index] = annotation

    return annotation_dict


def update_label_annoation(
    label_txt_path: str,
    image_annotation_dict: Dict[str, Dict[int, str]],
    folder_location: str,
) -> Tuple[List[str], List[str]]:
    updated_image_list = []
    label_list = put_txt_to_list(label_txt_path)

    for image in image_annotation_dict.keys():
        search_quary = folder_location + "/" + image
        image_label_line = None
        image_label_index = None

        for i, line in enumerate(label_list):
            if line.startswith(search_quary):
                image_label_line = line
                image_label_index = i
                break

        if image_label_line is None:
            print(f"Label not found for image: {image}")
            continue

        image_part = image_label_line.split("\t")[0]
        json_part = image_label_line.split("\t")[1]

        label_data = json.loads(json_part)
        cropImage_annotation_dict = image_annotation_dict[image]

        for index in cropImage_annotation_dict.keys():
            for i, item in enumerate(label_data):
                if i == index:
                    item["transcription"] = cropImage_annotation_dict[index]
                    break

        updated_label_line = (
            image_part + "\t" + json.dumps(label_data, ensure_ascii=False)
        )
        label_list[image_label_index] = updated_label_line

        updated_image_list.append(image)

    return label_list, updated_image_list


def cleaning_string(input_string):
    cleaned_string = input_string.replace("\n", "")

    result_string = cleaned_string + "\n"

    return result_string


def list_to_txt(lis: List[str], file_path: str) -> None:
    with open(file_path, "w") as file:
        for item in lis:
            clean_item = cleaning_string(item)
            file.write(clean_item)


def main() -> None:

    parser = argparse.ArgumentParser(description="Add the Image Folder.")
    parser.add_argument("--folder_path", type=str, help="Image Folder path")
    args = parser.parse_args()

    base_folder = args.folder_path
    crop_images_path = os.path.join(base_folder, "crop_img")
    folder_location = base_folder.split("/")[0]

    main_image_list = os.listdir(base_folder)
    main_image_list = [image for image in main_image_list if image[-4:] == ".jpg"]

    crop_images_list = os.listdir(crop_images_path)
    crop_images_list = [image for image in crop_images_list if image[-4:] == ".jpg"]

    ymal_location = os.path.join("complete_image.yml")
    if os.path.exists(ymal_location):

        with open(ymal_location, "r") as file:
            data = yaml.safe_load(file)
        completed_image_list = data["image_list"]
    else:

        completed_image_list = []

    completed_image_list

    updated_main_image_list = [
        image for image in main_image_list if image not in completed_image_list
    ]

    label_txt_path = os.path.join(base_folder, "Label.txt")
    rec_txt_path = os.path.join(base_folder, "rec_gt.txt")

    box_images_crop_image_dict = {}

    for image_name in updated_main_image_list:
        box_images_crop_image_dict[image_name] = get_image_crop_list(
            image_name, crop_images_list
        )
    box_images_crop_image_dict

    annotaion_dict = get_crop_images_annotations(
        box_images_crop_image_dict, crop_images_path
    )

    updated_rec_txt = update_rec_annotation(
        rec_txt_path, box_images_crop_image_dict, annotaion_dict
    )

    updated_label_txt, newly_updated_image_list = update_label_annoation(
        label_txt_path, annotaion_dict, folder_location
    )

    list_to_txt(updated_rec_txt, rec_txt_path)
    list_to_txt(updated_label_txt, label_txt_path)

    yml_save = {
        "image_list": list(set(completed_image_list + newly_updated_image_list))
    }

    with open("complete_image.yml", "w") as file:
        yaml.dump(yml_save, file)

    print("Updated Completed !!!!")


if __name__ == "__main__":
    main()
