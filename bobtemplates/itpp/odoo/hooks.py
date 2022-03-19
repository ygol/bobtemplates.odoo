# -*- coding: utf-8 -*-
# Copyright © 2016 ACSONE SA/NV
# Copyright 2019 Anvar Kildebekov <https://it-projects.info/team/fedoranvar>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ast
import datetime
import os
import re
from subprocess import check_output

from mrbob.bobexceptions import ValidationError
from mrbob.hooks import show_message
from pkg_resources import parse_version


def _dotted_to_camelcased(dotted):
    return "".join([s.capitalize() for s in dotted.split(".")])


def _dotted_to_underscored(dotted):
    return dotted.replace(".", "_")


def _dotted_to_camelwords(dotted):
    return " ".join([s.capitalize() for s in dotted.split(".")])


def _underscored_to_camelcased(underscored):
    return "".join([s.capitalize() for s in underscored.split("_")])


def _underscored_to_camelwords(underscored):
    return " ".join([s.capitalize() for s in underscored.split("_")])


def _spaced_to_underscored_and_lowered(spaced):
    return spaced.replace(" ", "_").lower()


def _spaced_to_unspaced_and_lowered(spaced):
    return spaced.replace(" ", "").lower()


def _delete_file(configurator, path):
    """remove file and remove it's directories if empty"""
    path = os.path.join(configurator.target_directory, path)
    os.remove(path)
    try:
        os.removedirs(os.path.dirname(path))
    except OSError:
        pass


def _open_file(configurator, file, mode="r"):
    file_path = os.path.join(configurator.target_directory, file)
    if not os.path.exists(file_path):
        raise ValidationError("{} not found".format(file_path))
    return open(file_path, mode)


def _load_manifest(configurator):
    with _open_file(configurator, "__manifest__.py") as f:
        return ast.literal_eval(f.read())


def _insert_manifest_item(configurator, key, item):
    """Insert an item in the list of an existing manifest key"""
    with _open_file(configurator, "__manifest__.py") as f:
        manifest = f.read()
    if item in ast.literal_eval(manifest).get(key, []):
        return
    pattern = """(["']{}["']:\\s*\\[)""".format(key)
    # TODO: it new item should added to the end of list
    repl = """\\1\n        '{}',""".format(item)
    manifest = re.sub(pattern, repl, manifest, re.MULTILINE)
    with _open_file(configurator, "__manifest__.py", "w") as f:
        f.write(manifest)


def _add_in_file_text(configurator, dir_path, to_file, import_string):
    init_path = os.path.join(configurator.target_directory, dir_path, to_file)
    variables = configurator.variables
    flag = "a"
    if os.path.exists(init_path):
        with open(init_path, "U") as f:
            init = f.read()
            if to_file == "assets.xml":
                flag = "w"
                idx = init.index("</odoo>")
                import_string = init[:idx] + import_string + "\n" + init[idx:]
    else:
        init = ""
        os.makedirs(os.path.split(init_path)[0], exist_ok=True)
        if to_file == "assets.xml":
            import_string = ("" "<odoo>\n{3}\n</odoo>\n").format(
                variables["copyright.year"],
                variables["copyright.name"],
                variables["copyright.github"],
                import_string,
            )
        if to_file == "ir.model.access.csv":
            import_string = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink{}".format(
                import_string
            )

    if import_string not in init.split("\n"):
        open(init_path, flag).write(import_string)


def _rm_suffix(suffix, configurator, path):
    path = os.path.join(configurator.target_directory, path)
    assert path.endswith(suffix)
    os.rename(path, path[: -len(suffix)])


#
# addon hooks
#
def pre_render_addon(configurator):
    variables = configurator.variables
    variables["odoo.version"] = int(variables["addon.version"])
    variables["addon.name_camelwords"] = _underscored_to_camelwords(
        _spaced_to_underscored_and_lowered(variables["addon.name"])
    )
    #
    # addon defaults
    #
    # [copyright.year] - year of creation
    variables["copyright.year"] = datetime.date.today().year
    # [addon.branch] - name of git-branch
    variables["addon.branch"] = str(variables["odoo.version"]) + ".0"


def post_render_addon(configurator):
    category_list = [
        "access",
        "barcode",
        "mail",
        "misc",
        "pos",
        "saas",
        "sync",
        "stock",
        "telegram",
        "website",
        "website_sale",
    ]
    variables = configurator.variables
    configurator.target_directory += "/" + variables["addon.technical_name"]
    if variables["addon.dependency"]:
        for mod in variables["addon.dependency"].split(", "):
            _insert_manifest_item(configurator, "depends", mod)
    # Handle icons in depends of technical_category
    _rm_suffix(
        "." + variables["addon.technical_category"],
        configurator,
        "static/description/icon.png." + variables["addon.technical_category"],
    )
    category_list.remove(variables["addon.technical_category"])
    for ctgr in category_list:
        _delete_file(configurator, "static/description/icon.png." + ctgr)
    # show message if any
    show_message(configurator)


#
# data hooks
#
def pre_render_data(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_data(configurator):
    variables = configurator.variables
    data_path = "data/{}.xml".format(variables["data.name_underscored"])
    _insert_manifest_item(configurator, "data", data_path)
    show_message(configurator)


#
# demo hooks
#
def pre_render_demo(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_demo(configurator):
    variables = configurator.variables
    demo_path = "demo/{}.xml".format(variables["demo.name_underscored"])
    _insert_manifest_item(configurator, "demo", demo_path)
    show_message(configurator)


#
# qweb hooks
#
def pre_render_qweb(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_qweb(configurator):
    variables = configurator.variables
    qweb_path = "static/src/xml/{}.xml".format(variables["qweb.name_underscored"])
    _insert_manifest_item(configurator, "qweb", qweb_path)
    show_message(configurator)


#
# view hooks
#
def pre_render_view(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_view(configurator):
    variables = configurator.variables
    xml_path = "views/{}.xml".format(variables["view.name_underscored"])
    _insert_manifest_item(configurator, "data", xml_path)
    show_message(configurator)


#
# model hooks
#
def pre_render_model(configurator):
    variables = configurator.variables
    variables["odoo.version"] = int(variables["addon.version"])
    variables["model.name_underscored"] = _dotted_to_underscored(
        variables["model.name_dotted"]
    )
    variables["model.name_camelcased"] = _dotted_to_camelcased(
        variables["model.name_dotted"]
    )
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )
    #
    # model defaults
    #


def post_render_model(configurator):
    variables = configurator.variables
    security_path = "security/ir.model.access.csv"
    # make sure the models package is imported from the addon root
    _add_in_file_text(configurator, "", "__init__.py", "from . import models")
    # add new model import in __init__.py
    import_string = "from . import {}".format(variables["model.name_underscored"])
    _add_in_file_text(configurator, "models", "__init__.py", import_string)
    if variables["model.security"]:
        import_string = (
            "\naccess_{0},access_{0},model_{0},base.group_user,1,1,1,1".format(
                variables["model.name_underscored"]
            )
        )
        _add_in_file_text(
            configurator, "security", "ir.model.access.csv", import_string
        )
        _insert_manifest_item(configurator, "data", security_path)
    # show message if any
    show_message(configurator)


#
# controller hooks
#
def pre_render_controller(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["odoo.version"] = int(variables["addon.version"])
    variables["controller.name_underscored"] = _dotted_to_underscored(
        variables["controller.name_dotted"]
    )
    variables["controller.name_camelcased"] = _dotted_to_camelcased(
        variables["controller.name_dotted"]
    )
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_controller(configurator):
    variables = configurator.variables
    # make sure the controllers package is imported from the addon root
    _add_in_file_text(configurator, "", "__init__.py", "from . import controllers")
    # add new model import in __init__.py
    import_string = "from . import {}".format(variables["controller.name_underscored"])
    _add_in_file_text(configurator, "controllers", "__init__.py", import_string)
    show_message(configurator)


#
# css hooks
#
def pre_render_css(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    category = variables["addon.technical_category"]
    if category == "pos":
        variables["css.inherit"] = "point_of_sale.assets"
    elif category in ["website", "website_sale"]:
        variables["css.inherit"] = "website.assets_frontend"
    else:
        variables["css.inherit"] = "web.assets_backend"
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_css(configurator):
    variables = configurator.variables
    script_text = """
    <template id="{0}" inherit_id="{1}">
        <xpath expr="." position="inside">
            <link rel="stylesheet" href="/{2}/static/src/css/{0}.css"/>
        </xpath>
    </template>
    """.format(
        variables["css.name_underscored"],
        variables["css.inherit"],
        variables["addon.name"],
    )
    _add_in_file_text(configurator, "views", "assets.xml", script_text)
    xml_path = "views/assets.xml".format(variables["css.name_underscored"])
    _insert_manifest_item(configurator, "data", xml_path)
    show_message(configurator)


#
# js hooks
#
def pre_render_js(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    category = variables["addon.technical_category"]
    if category == "pos":
        variables["js.inherit"] = "point_of_sale.assets"
    elif category in ["website", "website_sale"]:
        variables["js.inherit"] = category + ".assets_frontend"
    else:
        variables["js.inherit"] = "web.assets_backend"
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_js(configurator):
    variables = configurator.variables
    script_text = """
    <template id="{0}" inherit_id="{1}">
        <xpath expr="." position="inside">
            <script type="text/javascript" src="/{2}/static/src/js/{0}.js"></script>
        </xpath>
    </template>
    """.format(
        variables["js.name_underscored"],
        variables["js.inherit"],
        variables["addon.name"],
    )
    _add_in_file_text(configurator, "views", "assets.xml", script_text)
    assets_path = "views/assets.xml".format(variables["js.name_underscored"])
    _insert_manifest_item(configurator, "data", assets_path)
    # show message if any
    show_message(configurator)


#
# test hooks
#
def pre_render_test(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    category = variables["addon.category"]
    if category in ["website", "website_sale"]:
        variables["test.assets"] = "website.assets_frontend"
    else:
        variables["test.assets"] = "web.assets_backend"
    variables["odoo.version"] = int(variables["addon.version"])
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_test(configurator):
    variables = configurator.variables
    script_text = """
    <template id="test_{0}" inherit_id="{1}">
        <xpath expr="." position="inside">
            <script type="text/javascript" src="/{2}/static/src/js/test_{0}.js"></script>
        </xpath>
    </template>
    """.format(
        variables["test.name_underscored"],
        variables["test.assets"],
        variables["addon.name"],
    )
    _add_in_file_text(configurator, "views", "assets.xml", script_text)
    import_string = "from . import test_{}".format(variables["test.name_underscored"])
    _add_in_file_text(configurator, "tests", "__init__.py", import_string)
    assets_path = "views/assets.xml".format(variables["test.name_underscored"])
    js_path = "static/src/js/test_{}.js".format(variables["test.name_underscored"])
    if variables["test.tour"]:
        _insert_manifest_item(configurator, "data", assets_path)
    else:
        _delete_file(configurator, js_path)
        _delete_file(configurator, assets_path)
    # show message if any
    show_message(configurator)


#
# wizard hooks
#
def pre_render_wizard(configurator):
    _load_manifest(configurator)  # check manifest is present
    variables = configurator.variables
    variables["odoo.version"] = int(variables["addon.version"])
    variables["wizard.name_underscored"] = _dotted_to_underscored(
        variables["wizard.name_dotted"]
    )
    variables["wizard.name_camelcased"] = _dotted_to_camelcased(
        variables["wizard.name_dotted"]
    )
    variables["wizard.name_camelwords"] = _underscored_to_camelwords(
        variables["wizard.name_underscored"]
    )
    variables["addon.name"] = os.path.basename(
        os.path.normpath(configurator.target_directory)
    )


def post_render_wizard(configurator):
    variables = configurator.variables
    # make sure the wizards package is imported from the addon root
    _add_in_file_text(configurator, "", "__init__.py", "from . import wizards")
    # add new model import in __init__.py
    import_string = "from . import {}".format(variables["wizard.name_underscored"])
    _add_in_file_text(configurator, "wizards", "__init__.py", import_string)
    # views
    wizard_path = "wizards/{}.xml".format(variables["wizard.name_underscored"])
    _insert_manifest_item(configurator, "data", wizard_path)
    # show message if any
    show_message(configurator)
