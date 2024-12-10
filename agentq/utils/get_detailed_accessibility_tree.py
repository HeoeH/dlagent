import json
import os
import re
import traceback
from typing import Dict, List, Optional

from playwright.async_api import Page
from typing_extensions import Annotated, Any

from agentq.config.config import SOURCE_LOG_FOLDER_PATH
from agentq.core.web_driver.playwright import PlaywrightManager
from agentq.utils.logger import logger

space_delimited_mmid = re.compile(r"^[\d ]+$")


def is_space_delimited_mmid(s: str) -> bool:
    """
    Check if the given string matches the the mmid pattern of number space repeated.

    Parameters:
    - s (str): The string to check against the pattern.

    Returns:
    - bool: True if the string matches the pattern, False otherwise.
    """
    # Use fullmatch() to ensure the entire string matches the pattern
    return bool(space_delimited_mmid.fullmatch(s))

# async def __inject_attributes(page: Page):
#     """
#     Injects 'mmid' and 'aria-keyshortcuts' into all DOM elements. If an element already has an 'aria-keyshortcuts',
#     it renames it to 'orig-aria-keyshortcuts' before injecting the new 'aria-keyshortcuts'
#     This will be captured in the accessibility tree and thus make it easier to reconcile the tree with the DOM.
#     'aria-keyshortcuts' is choosen because it is not widely used aria attribute.
#     """

#     last_mmid = await page.evaluate("""() => {
#         const allElements = document.querySelectorAll('*');
#         let id = 0;
#         allElements.forEach(element => {
#             const origAriaAttribute = element.getAttribute('aria-keyshortcuts');
#             const mmid = `${++id}`;
#             element.setAttribute('mmid', mmid);
#             element.setAttribute('aria-keyshortcuts', mmid);
#             //console.log(`Injected 'mmid'into element with tag: ${element.tagName} and mmid: ${mmid}`);
#             if (origAriaAttribute) {
#                 element.setAttribute('orig-aria-keyshortcuts', origAriaAttribute);
#             }
#         });
#         return id;
#     }""")
#     logger.debug(f"Added MMID into {last_mmid} elements")
#     print(f"Added MMID into {last_mmid} elements")


# async def __fetch_dom_info(
#     page: Page, accessibility_tree: Dict[str, Any], only_input_fields: bool
# ):
#     """
#     Iterates over the accessibility tree, fetching additional information from the DOM based on 'mmid',
#     and constructs a new JSON structure with detailed information.

#     Args:
#         page (Page): The page object representing the web page.
#         accessibility_tree (Dict[str, Any]): The accessibility tree JSON structure.
#         only_input_fields (bool): Flag indicating whether to include only input fields in the new JSON structure.

#     Returns:
#         Dict[str, Any]: The pruned tree with detailed information from the DOM.
#     """

#     logger.debug("Reconciling the Accessibility Tree with the DOM")
#     # Define the attributes to fetch for each element
#     attributes = [
#         "name",
#         "aria-label",
#         "placeholder",
#         "mmid",
#         "id",
#         "for",
#         "data-testid",
#     ]
#     backup_attributes = []  # if the attributes are not found, then try to get these attributes
#     tags_to_ignore = [
#         "head",
#         "style",
#         "script",
#         "link",
#         "meta",
#         "noscript",
#         "template",
#         "iframe",
#         "g",
#         "main",
#         "c-wiz",
#         "svg",
#         "path",
#     ]
#     attributes_to_delete = ["level", "multiline", "haspopup", "id", "for"]
#     ids_to_ignore = ["agentDriveAutoOverlay"]

#     # Recursive function to process each node in the accessibility tree
#     async def process_node(node: Dict[str, Any]):
#         if "children" in node:
#             for child in node["children"]:
#                 await process_node(child)

#         # Use 'name' attribute from the accessibility node as 'mmid'
#         mmid_temp: str = node.get("keyshortcuts")  # type: ignore

#         # If the name has multiple mmids, take the last one
#         if mmid_temp and is_space_delimited_mmid(mmid_temp):
#             # TODO: consider if we should grab each of the mmids and process them separately as seperate nodes copying this node's attributes
#             mmid_temp = mmid_temp.split(" ")[-1]

#         # focusing on nodes with mmid, which is the attribute we inject
#         try:
#             mmid = int(mmid_temp)
#         except (ValueError, TypeError):
#             # logger.error(f"'name attribute contains \"{node.get('name')}\", which is not a valid numeric mmid. Adding node as is: {node}")
#             return node.get("name")

#         if node["role"] == "menuitem":
#             return node.get("name")

#         if node.get("role") == "dialog" and node.get("modal") == True:  # noqa: E712
#             node["important information"] = (
#                 "This is a modal dialog. Please interact with this dialog and close it to be able to interact with the full page (e.g. by pressing the close button or selecting an option)."
#             )

#         if mmid:
#             # Determine if we need to fetch 'innerText' based on the absence of 'children' in the accessibility node
#             should_fetch_inner_text = "children" not in node

#             js_code = """
#             (input_params) => {
#                 const should_fetch_inner_text = input_params.should_fetch_inner_text;
#                 const mmid = input_params.mmid;
#                 const attributes = input_params.attributes;
#                 const tags_to_ignore = input_params.tags_to_ignore;
#                 const ids_to_ignore = input_params.ids_to_ignore;

#                 const element = document.querySelector(`[mmid="${mmid}"]`);

#                 if (!element) {
#                     console.log(`No element found with mmid: ${mmid}`);
#                     return null;
#                 }

#                 if (ids_to_ignore.includes(element.id)) {
#                     console.log(`Ignoring element with id: ${element.id}`, element);
#                     return null;
#                 }
#                 //Ignore "option" because it would have been processed with the select element
#                 if (tags_to_ignore.includes(element.tagName.toLowerCase()) || element.tagName.toLowerCase() === "option") return null;

#                 let attributes_to_values = {
#                     'tag': element.tagName.toLowerCase() // Always include the tag name
#                 };

#                 // If the element is an input, include its type as well
#                 if (element.tagName.toLowerCase() === 'input') {
#                     attributes_to_values['tag_type'] = element.type; // This will capture 'checkbox', 'radio', etc.
#                 }
#                 else if (element.tagName.toLowerCase() === 'select') {
#                     attributes_to_values["mmid"] = element.getAttribute('mmid');
#                     attributes_to_values["role"] = "combobox";
#                     attributes_to_values["options"] = [];

#                     for (const option of element.options) {
#                         let option_attributes_to_values = {
#                             "mmid": option.getAttribute('mmid'),
#                             "text": option.text,
#                             "value": option.value,
#                             "selected": option.selected
#                         };
#                         attributes_to_values["options"].push(option_attributes_to_values);
#                     }
#                     return attributes_to_values;
#                 }

#                 for (const attribute of attributes) {
#                     let value = element.getAttribute(attribute);

#                     if(value){
#                         /*
#                         if(attribute === 'href'){
#                             value = value.split('?')[0]
#                         }
#                         */
#                         attributes_to_values[attribute] = value;
#                     }
#                 }

#                 if (should_fetch_inner_text && element.innerText) {
#                     attributes_to_values['description'] = element.innerText;
#                 }

#                 let role = element.getAttribute('role');
#                 if(role==='listbox' || element.tagName.toLowerCase()=== 'ul'){
#                     let children=element.children;
#                     let filtered_children = Array.from(children).filter(child => child.getAttribute('role') === 'option');
#                     console.log("Listbox or ul found: ", filtered_children);
#                     let attributes_to_include = ['mmid', 'role', 'aria-label','value'];
#                     attributes_to_values["additional_info"]=[]
#                     for (const child of children) {
#                         let children_attributes_to_values = {};

#                         for (let attr of child.attributes) {
#                             // If the attribute is not in the predefined list, add it to children_attributes_to_values
#                             if (attributes_to_include.includes(attr.name)) {
#                                 children_attributes_to_values[attr.name] = attr.value;
#                             }
#                         }

#                         attributes_to_values["additional_info"].push(children_attributes_to_values);
#                     }
#                 }
#                 // Check if attributes_to_values contains more than just 'name', 'role', and 'mmid'
#                 const keys = Object.keys(attributes_to_values);
#                 const minimalKeys = ['tag', 'mmid'];
#                 const hasMoreThanMinimalKeys = keys.length > minimalKeys.length || keys.some(key => !minimalKeys.includes(key));

#                 if (!hasMoreThanMinimalKeys) {
#                     //If there were no attributes found, then try to get the backup attributes
#                     for (const backupAttribute of input_params.backup_attributes) {
#                         let value = element.getAttribute(backupAttribute);
#                         if(value){
#                             attributes_to_values[backupAttribute] = value;
#                         }
#                     }

#                     //if even the backup attributes are not found, then return null, which will cause this element to be skipped
#                     if(Object.keys(attributes_to_values).length <= minimalKeys.length) {
#                         if (element.tagName.toLowerCase() === 'button') {
#                                 attributes_to_values["mmid"] = element.getAttribute('mmid');
#                                 attributes_to_values["role"] = "button";
#                                 attributes_to_values["additional_info"] = [];
#                                 let children=element.children;
#                                 let attributes_to_exclude = ['width', 'height', 'path', 'class', 'viewBox', 'mmid']

#                                 // Check if the button has no text and no attributes
#                                 if (element.innerText.trim() === '') {

#                                     for (const child of children) {
#                                         let children_attributes_to_values = {};

#                                         for (let attr of child.attributes) {
#                                             // If the attribute is not in the predefined list, add it to children_attributes_to_values
#                                             if (!attributes_to_exclude.includes(attr.name)) {
#                                                 children_attributes_to_values[attr.name] = attr.value;
#                                             }
#                                         }

#                                         attributes_to_values["additional_info"].push(children_attributes_to_values);
#                                     }
#                                     console.log("Button with no text and no attributes: ", attributes_to_values);
#                                     return attributes_to_values;
#                                 }
#                         }

#                         return null; // Return null if only minimal keys are present
#                     }
#                 }
#                 return attributes_to_values;
#             }
#             """

#             # Fetch attributes and possibly 'innerText' from the DOM element by 'mmid'
#             element_attributes = await page.evaluate(
#                 js_code,
#                 {
#                     "mmid": mmid,
#                     "attributes": attributes,
#                     "backup_attributes": backup_attributes,
#                     "should_fetch_inner_text": should_fetch_inner_text,
#                     "tags_to_ignore": tags_to_ignore,
#                     "ids_to_ignore": ids_to_ignore,
#                 },
#             )

#             if "keyshortcuts" in node:
#                 del node["keyshortcuts"]  # remove keyshortcuts since it is not needed

#             node["mmid"] = mmid

#             # Update the node with fetched information
#             if element_attributes:
#                 node.update(element_attributes)

#                 # check if 'name' and 'mmid' are the same
#                 if (
#                     node.get("name") == node.get("mmid")
#                     and node.get("role") != "textbox"
#                 ):
#                     del node["name"]  # Remove 'name' from the node

#                 if (
#                     "name" in node
#                     and "description" in node
#                     and (
#                         node["name"] == node["description"]
#                         or node["name"] == node["description"].replace("\n", " ")
#                         or node["description"].replace("\n", "") in node["name"]
#                     )
#                 ):
#                     del node[
#                         "description"
#                     ]  # if the name is same as description, then remove the description to avoid duplication

#                 if (
#                     "name" in node
#                     and "aria-label" in node
#                     and node["aria-label"] in node["name"]
#                 ):
#                     del node[
#                         "aria-label"
#                     ]  # if the name is same as the aria-label, then remove the aria-label to avoid duplication

#                 if "name" in node and "text" in node and node["name"] == node["text"]:
#                     del node[
#                         "text"
#                     ]  # if the name is same as the text, then remove the text to avoid duplication

#                 if (
#                     node.get("tag") == "select"
#                 ):  # children are not needed for select menus since "options" attriburte is already added
#                     node.pop("children", None)
#                     node.pop("role", None)
#                     node.pop("description", None)

#                 # role and tag can have the same info. Get rid of role if it is the same as tag
#                 if node.get("role") == node.get("tag"):
#                     del node["role"]

#                 # avoid duplicate aria-label
#                 if (
#                     node.get("aria-label")
#                     and node.get("placeholder")
#                     and node.get("aria-label") == node.get("placeholder")
#                 ):
#                     del node["aria-label"]

#                 if node.get("role") == "link":
#                     del node["role"]
#                     if node.get("description"):
#                         node["text"] = node["description"]
#                         del node["description"]

#                 # textbox just means a text input and that is expressed well enough with the rest of the attributes returned
#                 # if node.get('role') == "textbox":
#                 #    del node['role']

#                 if node.get("role") == "textbox":
#                     # get the id attribute of this field from the DOM
#                     if "id" in element_attributes and element_attributes["id"]:
#                         # find if there is an element in the DOM that has this id in aria-labelledby.
#                         js_code = """
#                         (inputParams) => {
#                             let referencingElements = [];
#                             const referencedElement = document.querySelector(`[aria-labelledby="${inputParams.aria_labelled_by_query_value}"]`);
#                             if(referencedElement) {
#                                 const mmid = referencedElement.getAttribute('mmid');
#                                 if (mmid) {
#                                     return {"mmid": mmid, "tag": referencedElement.tagName.toLowerCase()};
#                                 }
#                             }
#                             return null;
#                         }
#                         """
#                     # textbox just means a text input and that is expressed well enough with the rest of the attributes returned
#                     # del node['role']

#             # remove attributes that are not needed once processing of a node is complete
#             for attribute_to_delete in attributes_to_delete:
#                 if attribute_to_delete in node:
#                     node.pop(attribute_to_delete, None)
#         else:
#             logger.debug(f"No element found with mmid: {mmid}, deleting node: {node}")
#             node["marked_for_deletion_by_mm"] = True

#     # Process each node in the tree starting from the root
#     await process_node(accessibility_tree)

#     pruned_tree = __prune_tree(accessibility_tree, only_input_fields)

#     logger.debug("Reconciliation complete")
#     return pruned_tree




#改过第二次的有框的
async def __inject_attributes(page: Page):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except TimeoutError:
        print("DOM content loaded wait timed out, proceeding without waiting.")

    script = """
    () => {
        window.onkeydown = function(e) {
            if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea') {
                e.preventDefault();
            }
        };
    }
    """
    await page.evaluate(script)

    result = await page.evaluate("""
        () => {
            let labels = [];
            let markedElements = new Set(); // 用于存储已标记的元素，防止重复标记

            function markPage() {
                var bodyRect = document.body.getBoundingClientRect();

                var items = Array.prototype.slice.call(
                    document.querySelectorAll('*')
                ).map(function(element) {
                    var vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
                    var vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

                    var rects = [...element.getClientRects()].filter(bb => {
                        var center_x = bb.left + bb.width / 2;
                        var center_y = bb.top + bb.height / 2;
                        var elAtCenter = document.elementFromPoint(center_x, center_y);

                        return elAtCenter === element || element.contains(elAtCenter);
                    }).map(bb => {
                        const rect = {
                            left: Math.max(0, bb.left),
                            top: Math.max(0, bb.top),
                            right: Math.min(vw, bb.right),
                            bottom: Math.min(vh, bb.bottom)
                        };
                        return {
                            ...rect,
                            width: rect.right - rect.left,
                            height: rect.bottom - rect.top
                        }
                    });

                    var area = rects.reduce((acc, rect) => acc + rect.width * rect.height, 0);

                    return {
                        element: element,
                        include: 
                            (element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT") ||
                            (element.tagName === "BUTTON" || element.tagName === "A" || (element.onclick != null) || window.getComputedStyle(element).cursor == "pointer") ||
                            (element.tagName === "IFRAME" || element.tagName === "VIDEO" || element.tagName === "LI" || element.tagName === "TD" || element.tagName === "OPTION"),
                        area,
                        rects,
                        text: element.textContent.trim().replace(/\s{2,}/g, ' '),
                        tagName: element.tagName,
                        type: element.getAttribute("type") || '',
                        ariaLabel: element.getAttribute("aria-label") || ''
                    };
                }).filter(item =>
                    item.include && (item.area >= 20)
                );

                // Filter out unnecessary buttons and elements
                const buttons = Array.from(document.querySelectorAll('button, a, input[type="button"], div[role="button"]'));
                items = items.filter(x => !buttons.some(y => items.some(z => z.element === y) && y.contains(x.element) && !(x.element === y)));
                items = items.filter(x => 
                    !(x.element.parentNode && 
                    x.element.parentNode.tagName === 'SPAN' && 
                    x.element.parentNode.children.length === 1 && 
                    x.element.parentNode.getAttribute('role') &&
                    items.some(y => y.element === x.element.parentNode)));

                items = items.filter(x => !items.some(y => x.element.contains(y.element) && !(x == y)));

                let lastMmid = 0;
                items.forEach(function(item, index) {
                    // Debugging output to check if element is processed
                    console.log("Processing item:", item.element);

                    if (markedElements.has(item.element)) return; // Skip already marked elements

                    item.rects.forEach((bbox) => {
                        // Generate random color for floating borders
                        var borderColor = getRandomColor(index);

                        // Create the floating border element
                        let newElement = document.createElement("div");
                        newElement.style.outline = `2px dashed ${borderColor}`;
                        newElement.style.position = "fixed";
                        newElement.style.left = bbox.left + "px";
                        newElement.style.top = bbox.top + "px";
                        newElement.style.width = bbox.width + "px";
                        newElement.style.height = bbox.height + "px";
                        newElement.style.pointerEvents = "none";
                        newElement.style.boxSizing = "border-box";
                        newElement.style.zIndex = 2147483647;

                        // Add floating label at the corner
                        var label = document.createElement("span");
                        label.textContent = index;
                        label.style.position = "absolute";
                        label.style.top = Math.max(-19, -bbox.top) + "px";
                        label.style.left = Math.min(Math.floor(bbox.width / 5), 2) + "px";
                        label.style.background = borderColor;
                        label.style.color = "white";
                        label.style.padding = "2px 4px";
                        label.style.fontSize = "12px";
                        label.style.borderRadius = "2px";
                        newElement.appendChild(label);

                        // Inject mmid to the marked elements
                        const origAriaAttribute = item.element.getAttribute('aria-keyshortcuts');
                        lastMmid++;
                        item.element.setAttribute('mmid', lastMmid);
                        item.element.setAttribute('aria-keyshortcuts', lastMmid);
                        if (origAriaAttribute) {
                            item.element.setAttribute('orig-aria-keyshortcuts', origAriaAttribute);
                        }

                        document.body.appendChild(newElement);
                        labels.push(newElement);
                    });

                    // Mark the element to avoid duplication
                    markedElements.add(item.element);
                });

                return lastMmid;
            }

            // Function to generate random colors
            function getRandomColor(index) {
                var letters = '0123456789ABCDEF';
                var color = '#';
                for (var i = 0; i < 6; i++) {
                    color += letters[Math.floor(Math.random() * 16)];
                }
                return color;
            }

            // Initial invocation of markPage
            const lastMmid = markPage();
            console.log("Initial mmid injection done, last mmid:", lastMmid);

            // Create MutationObserver instance to handle dynamically added elements
            const observer = new MutationObserver((mutations) => {
                const newElements = Array.from(mutations)
                    .flatMap(mutation => Array.from(mutation.addedNodes))
                    .filter(node => node.nodeType === Node.ELEMENT_NODE && node.matches('button, a[href], input, select, textarea, [contenteditable], [tabindex], [role="button"], [role="link"], [role="checkbox"], [role="menuitem"], [role="option"], [role="radio"], [role="switch"], [role="tab"], [role="treeitem"]'));

                newElements.forEach(element => {
                    // Check if element is already marked
                    if (markedElements.has(element)) return;

                    // Inject mmid if not marked yet
                    const origAriaAttribute = element.getAttribute('aria-keyshortcuts');
                    lastMmid++;
                    element.setAttribute('mmid', lastMmid);
                    element.setAttribute('aria-keyshortcuts', lastMmid);
                    if (origAriaAttribute) {
                        element.setAttribute('orig-aria-keyshortcuts', origAriaAttribute);
                    }

                    // Mark the element as processed
                    markedElements.add(element);
                });
            });

            // Start observing DOM changes
            observer.observe(document.body, { childList: true, subtree: true });
            console.log("MutationObserver started");

            return lastMmid;
        }
    """)

    print(
        "Added MMID into elements dynamically and marked them with floating borders and labels"
    )
    return result


# async def __inject_attributes(page: Page):
#     try:
#         await page.wait_for_load_state('domcontentloaded', timeout=10000)
#     except TimeoutError:
#         print("DOM content loaded wait timed out, proceeding without waiting.")
# await page.evaluate("""
#     () => {
#         const injectMMID = (elements, startId = 0) => {
#             let id = startId;
#             elements.forEach(element => {
#                 const origAriaAttribute = element.getAttribute('aria-keyshortcuts');
#                 const mmid = `${++id}`;
#                 element.setAttribute('mmid', mmid);
#                 element.setAttribute('aria-keyshortcuts', mmid);
#                 if (origAriaAttribute) {
#                     element.setAttribute('orig-aria-keyshortcuts', origAriaAttribute);
#                 }
#             });
#             return id;
#         };

#         const interactiveSelectors = [
#             'button', 'a[href]', 'input', 'select', 'textarea',
#             '[contenteditable]', '[tabindex]', '[role="button"]', '[role="link"]',
#             '[role="checkbox"]', '[role="menuitem"]', '[role="option"]', '[role="radio"]',
#             '[role="switch"]', '[role="tab"]', '[role="treeitem"]'
#         ].join(',');

#         // 初始注入
#         const initialElements = document.querySelectorAll(interactiveSelectors);
#         const lastMmid = injectMMID(initialElements);

#         // 创建 MutationObserver 实例
#         const observer = new MutationObserver((mutations) => {
#             const newElements = Array.from(mutations)
#                 .flatMap(mutation => Array.from(mutation.addedNodes))
#                 .filter(node => node.nodeType === Node.ELEMENT_NODE && node.matches(interactiveSelectors));
#             if (newElements.length > 0) {
#                 injectMMID(newElements, lastMmid);
#             }
#         });

#         // 开始观察 DOM 变化
#         observer.observe(document.body, { childList: true, subtree: true });

#         return lastMmid;
#     }
# """)
# print(f"Added MMID into elements dynamically")


async def __fetch_dom_info(
    page: Page, accessibility_tree: Dict[str, Any], only_input_fields: bool
):
    """
    Iterates over the accessibility tree, fetching additional information from the DOM based on 'mmid',
    and constructs a new JSON structure with detailed information.

    Args:
        page (Page): The page object representing the web page.
        accessibility_tree (Dict[str, Any]): The accessibility tree JSON structure.
        only_input_fields (bool): Flag indicating whether to include only input fields in the new JSON structure.

    Returns:
        Dict[str, Any]: The pruned tree with detailed information from the DOM.
    """

    logger.debug("Reconciling the Accessibility Tree with the DOM")
    # Define the attributes to fetch for each element
    attributes = [
        "name",
        "aria-label",
        "placeholder",
        "mmid",
        "id",
        "for",
        "data-testid",
    ]
    backup_attributes = []  # if the attributes are not found, then try to get these attributes
    tags_to_ignore = [
        "head",
        "style",
        "script",
        "link",
        "meta",
        "noscript",
        "template",
        "iframe",
        "g",
        "main",
        "c-wiz",
        "svg",
        "path",
    ]
    attributes_to_delete = ["level", "multiline", "haspopup", "id", "for"]
    ids_to_ignore = ["agentDriveAutoOverlay"]

    # Recursive function to process each node in the accessibility tree
    async def process_node(node: Dict[str, Any]):
        if "children" in node:
            for child in node["children"]:
                await process_node(child)

        # Use 'name' attribute from the accessibility node as 'mmid'
        mmid_temp: str = node.get("keyshortcuts")  # type: ignore

        # If the name has multiple mmids, take the last one
        if mmid_temp and is_space_delimited_mmid(mmid_temp):
            # TODO: consider if we should grab each of the mmids and process them separately as seperate nodes copying this node's attributes
            mmid_temp = mmid_temp.split(" ")[-1]

        # focusing on nodes with mmid, which is the attribute we inject
        try:
            mmid = int(mmid_temp)
        except (ValueError, TypeError):
            # logger.error(f"'name attribute contains \"{node.get('name')}\", which is not a valid numeric mmid. Adding node as is: {node}")
            return node.get("name")

        if node["role"] == "menuitem":
            return node.get("name")

        if node.get("role") == "dialog" and node.get("modal") == True:  # noqa: E712
            node["important information"] = (
                "This is a modal dialog. Please interact with this dialog and close it to be able to interact with the full page (e.g. by pressing the close button or selecting an option)."
            )

        if mmid:
            # Determine if we need to fetch 'innerText' based on the absence of 'children' in the accessibility node
            should_fetch_inner_text = "children" not in node

            js_code = """
            (input_params) => {
                const should_fetch_inner_text = input_params.should_fetch_inner_text;
                const mmid = input_params.mmid;
                const attributes = input_params.attributes;
                const tags_to_ignore = input_params.tags_to_ignore;
                const ids_to_ignore = input_params.ids_to_ignore;

                const element = document.querySelector(`[mmid="${mmid}"]`);

                if (!element) {
                    console.log(`No element found with mmid: ${mmid}`);
                    return null;
                }

                if (ids_to_ignore.includes(element.id)) {
                    console.log(`Ignoring element with id: ${element.id}`, element);
                    return null;
                }
                //Ignore "option" because it would have been processed with the select element
                if (tags_to_ignore.includes(element.tagName.toLowerCase()) || element.tagName.toLowerCase() === "option") return null;

                let attributes_to_values = {
                    'tag': element.tagName.toLowerCase() // Always include the tag name
                };

                // If the element is an input, include its type as well
                if (element.tagName.toLowerCase() === 'input') {
                    attributes_to_values['tag_type'] = element.type; // This will capture 'checkbox', 'radio', etc.
                }
                else if (element.tagName.toLowerCase() === 'select') {
                    attributes_to_values["mmid"] = element.getAttribute('mmid');
                    attributes_to_values["role"] = "combobox";
                    attributes_to_values["options"] = [];

                    for (const option of element.options) {
                        let option_attributes_to_values = {
                            "mmid": option.getAttribute('mmid'),
                            "text": option.text,
                            "value": option.value,
                            "selected": option.selected
                        };
                        attributes_to_values["options"].push(option_attributes_to_values);
                    }
                    return attributes_to_values;
                }

                for (const attribute of attributes) {
                    let value = element.getAttribute(attribute);

                    if(value){
                        /*
                        if(attribute === 'href'){
                            value = value.split('?')[0]
                        }
                        */
                        attributes_to_values[attribute] = value;
                    }
                }

                if (should_fetch_inner_text && element.innerText) {
                    attributes_to_values['description'] = element.innerText;
                }

                let role = element.getAttribute('role');
                if(role==='listbox' || element.tagName.toLowerCase()=== 'ul'){
                    let children=element.children;
                    let filtered_children = Array.from(children).filter(child => child.getAttribute('role') === 'option');
                    console.log("Listbox or ul found: ", filtered_children);
                    let attributes_to_include = ['mmid', 'role', 'aria-label','value'];
                    attributes_to_values["additional_info"]=[]
                    for (const child of children) {
                        let children_attributes_to_values = {};

                        for (let attr of child.attributes) {
                            // If the attribute is not in the predefined list, add it to children_attributes_to_values
                            if (attributes_to_include.includes(attr.name)) {
                                children_attributes_to_values[attr.name] = attr.value;
                            }
                        }

                        attributes_to_values["additional_info"].push(children_attributes_to_values);
                    }
                }
                // Check if attributes_to_values contains more than just 'name', 'role', and 'mmid'
                const keys = Object.keys(attributes_to_values);
                const minimalKeys = ['tag', 'mmid'];
                const hasMoreThanMinimalKeys = keys.length > minimalKeys.length || keys.some(key => !minimalKeys.includes(key));

                if (!hasMoreThanMinimalKeys) {
                    //If there were no attributes found, then try to get the backup attributes
                    for (const backupAttribute of input_params.backup_attributes) {
                        let value = element.getAttribute(backupAttribute);
                        if(value){
                            attributes_to_values[backupAttribute] = value;
                        }
                    }

                    //if even the backup attributes are not found, then return null, which will cause this element to be skipped
                    if(Object.keys(attributes_to_values).length <= minimalKeys.length) {
                        if (element.tagName.toLowerCase() === 'button') {
                                attributes_to_values["mmid"] = element.getAttribute('mmid');
                                attributes_to_values["role"] = "button";
                                attributes_to_values["additional_info"] = [];
                                let children=element.children;
                                let attributes_to_exclude = ['width', 'height', 'path', 'class', 'viewBox', 'mmid']

                                // Check if the button has no text and no attributes
                                if (element.innerText.trim() === '') {

                                    for (const child of children) {
                                        let children_attributes_to_values = {};

                                        for (let attr of child.attributes) {
                                            // If the attribute is not in the predefined list, add it to children_attributes_to_values
                                            if (!attributes_to_exclude.includes(attr.name)) {
                                                children_attributes_to_values[attr.name] = attr.value;
                                            }
                                        }

                                        attributes_to_values["additional_info"].push(children_attributes_to_values);
                                    }
                                    console.log("Button with no text and no attributes: ", attributes_to_values);
                                    return attributes_to_values;
                                }
                        }

                        return null; // Return null if only minimal keys are present
                    }
                }
                return attributes_to_values;
            }
            """

            # Fetch attributes and possibly 'innerText' from the DOM element by 'mmid'
            element_attributes = await page.evaluate(
                js_code,
                {
                    "mmid": mmid,
                    "attributes": attributes,
                    "backup_attributes": backup_attributes,
                    "should_fetch_inner_text": should_fetch_inner_text,
                    "tags_to_ignore": tags_to_ignore,
                    "ids_to_ignore": ids_to_ignore,
                },
            )

            if "keyshortcuts" in node:
                del node["keyshortcuts"]  # remove keyshortcuts since it is not needed

            node["mmid"] = mmid

            # Update the node with fetched information
            if element_attributes:
                node.update(element_attributes)

                # check if 'name' and 'mmid' are the same
                if (
                    node.get("name") == node.get("mmid")
                    and node.get("role") != "textbox"
                ):
                    del node["name"]  # Remove 'name' from the node

                if (
                    "name" in node
                    and "description" in node
                    and (
                        node["name"] == node["description"]
                        or node["name"] == node["description"].replace("\n", " ")
                        or node["description"].replace("\n", "") in node["name"]
                    )
                ):
                    del node[
                        "description"
                    ]  # if the name is same as description, then remove the description to avoid duplication

                if (
                    "name" in node
                    and "aria-label" in node
                    and node["aria-label"] in node["name"]
                ):
                    del node[
                        "aria-label"
                    ]  # if the name is same as the aria-label, then remove the aria-label to avoid duplication

                if "name" in node and "text" in node and node["name"] == node["text"]:
                    del node[
                        "text"
                    ]  # if the name is same as the text, then remove the text to avoid duplication

                if (
                    node.get("tag") == "select"
                ):  # children are not needed for select menus since "options" attriburte is already added
                    node.pop("children", None)
                    node.pop("role", None)
                    node.pop("description", None)

                # role and tag can have the same info. Get rid of role if it is the same as tag
                if node.get("role") == node.get("tag"):
                    del node["role"]

                # avoid duplicate aria-label
                if (
                    node.get("aria-label")
                    and node.get("placeholder")
                    and node.get("aria-label") == node.get("placeholder")
                ):
                    del node["aria-label"]

                if node.get("role") == "link":
                    del node["role"]
                    if node.get("description"):
                        node["text"] = node["description"]
                        del node["description"]

                # textbox just means a text input and that is expressed well enough with the rest of the attributes returned
                # if node.get('role') == "textbox":
                #    del node['role']

                if node.get("role") == "textbox":
                    # get the id attribute of this field from the DOM
                    if "id" in element_attributes and element_attributes["id"]:
                        # find if there is an element in the DOM that has this id in aria-labelledby.
                        js_code = """
                        (inputParams) => {
                            let referencingElements = [];
                            const referencedElement = document.querySelector(`[aria-labelledby="${inputParams.aria_labelled_by_query_value}"]`);
                            if(referencedElement) {
                                const mmid = referencedElement.getAttribute('mmid');
                                if (mmid) {
                                    return {"mmid": mmid, "tag": referencedElement.tagName.toLowerCase()};
                                }
                            }
                            return null;
                        }
                        """
                    # textbox just means a text input and that is expressed well enough with the rest of the attributes returned
                    # del node['role']

            # remove attributes that are not needed once processing of a node is complete
            for attribute_to_delete in attributes_to_delete:
                if attribute_to_delete in node:
                    node.pop(attribute_to_delete, None)
        else:
            logger.debug(f"No element found with mmid: {mmid}, deleting node: {node}")
            node["marked_for_deletion_by_mm"] = True

    # Process each node in the tree starting from the root
    await process_node(accessibility_tree)

    pruned_tree = __prune_tree(accessibility_tree, only_input_fields)

    logger.debug("Reconciliation complete")
    return pruned_tree


async def __fetch_dom_info(
    page: Page, accessibility_tree: Dict[str, Any], only_input_fields: bool
):
    logger.debug("Reconciling the Accessibility Tree with the DOM")
    # Define the attributes to fetch for each element
    attributes = [
        "name",
        "aria-label",
        "placeholder",
        "mmid",
        "id",
        "for",
        "data-testid",
    ]
    backup_attributes = []  # if the attributes are not found, then try to get these attributes
    tags_to_ignore = [
        "head",
        "style",
        "script",
        "link",
        "meta",
        "noscript",
        "template",
        "iframe",
        "g",
        "main",
        "c-wiz",
        "svg",
        "path",
    ]
    attributes_to_delete = ["level", "multiline", "haspopup", "id", "for"]
    ids_to_ignore = ["agentDriveAutoOverlay"]

    # Recursive function to process each node in the accessibility tree
    async def process_node(node: Dict[str, Any]):
        if "children" in node:
            for child in node["children"]:
                await process_node(child)

        mmid_temp: str = node.get("keyshortcuts")  # type: ignore
        if mmid_temp and is_space_delimited_mmid(mmid_temp):
            mmid_temp = mmid_temp.split(" ")[-1]

        try:
            mmid = int(mmid_temp)
        except (ValueError, TypeError):
            return node.get("name")

        if node["role"] == "menuitem":
            return node.get("name")

        if node.get("role") == "dialog" and node.get("modal") == True:  # noqa: E712
            node["important information"] = (
                "This is a modal dialog. Please interact with this dialog and close it to be able to interact with the full page (e.g. by pressing the close button or selecting an option)."
            )

        if mmid:
            should_fetch_inner_text = "children" not in node

            js_code = """
            (input_params) => {
                const mmid = input_params.mmid;
                const attributes = input_params.attributes;
                const tags_to_ignore = input_params.tags_to_ignore;
                const ids_to_ignore = input_params.ids_to_ignore;
                const should_fetch_inner_text = input_params.should_fetch_inner_text;

                const element = document.querySelector(`[mmid="${mmid}"]`);

                if (!element) {
                    console.log(`No element found with mmid: ${mmid}`);
                    return null;
                }

                if (ids_to_ignore.includes(element.id)) {
                    console.log(`Ignoring element with id: ${element.id}`, element);
                    return null;
                }

                // Define valid tags based on the filtering conditions
                const validTags = [
                    "INPUT", "TEXTAREA", "SELECT", "BUTTON", "A", "IFRAME", "VIDEO", "LI", "TD", "OPTION"
                ];

                // Check if the element's tag is valid
                if (!validTags.includes(element.tagName) && 
                    !(element.tagName === "A" && element.onclick) &&
                    !(window.getComputedStyle(element).cursor === "pointer")) {
                    return null;  // If the element does not match the filtering conditions, skip it
                }

                let attributes_to_values = {
                    'tag': element.tagName.toLowerCase() // Always include the tag name
                };

                if (element.tagName.toLowerCase() === 'input') {
                    attributes_to_values['tag_type'] = element.type;
                }
                else if (element.tagName.toLowerCase() === 'select') {
                    attributes_to_values["mmid"] = element.getAttribute('mmid');
                    attributes_to_values["role"] = "combobox";
                    attributes_to_values["options"] = [];

                    for (const option of element.options) {
                        let option_attributes_to_values = {
                            "mmid": option.getAttribute('mmid'),
                            "text": option.text,
                            "value": option.value,
                            "selected": option.selected
                        };
                        attributes_to_values["options"].push(option_attributes_to_values);
                    }
                    return attributes_to_values;
                }

                for (const attribute of attributes) {
                    let value = element.getAttribute(attribute);

                    if(value){
                        attributes_to_values[attribute] = value;
                    }
                }

                if (should_fetch_inner_text && element.innerText) {
                    attributes_to_values['description'] = element.innerText;
                }

                // Only return attributes if mmid is present
                if (attributes_to_values["mmid"]) {
                    return attributes_to_values;
                }

                return null;  // Skip if no mmid found
            }
            """

            # Fetch attributes and possibly 'innerText' from the DOM element by 'mmid'
            element_attributes = await page.evaluate(
                js_code,
                {
                    "mmid": mmid,
                    "attributes": attributes,
                    "backup_attributes": backup_attributes,
                    "should_fetch_inner_text": should_fetch_inner_text,
                    "tags_to_ignore": tags_to_ignore,
                    "ids_to_ignore": ids_to_ignore,
                },
            )

            if "keyshortcuts" in node:
                del node["keyshortcuts"]

            node["mmid"] = mmid

            if element_attributes:
                node.update(element_attributes)

                if (
                    node.get("name") == node.get("mmid")
                    and node.get("role") != "textbox"
                ):
                    del node["name"]

                if (
                    "name" in node
                    and "description" in node
                    and (
                        node["name"] == node["description"]
                        or node["name"] == node["description"].replace("\n", " ")
                    )
                ):
                    del node["description"]

                if (
                    "name" in node
                    and "aria-label" in node
                    and node["aria-label"] in node["name"]
                ):
                    del node["aria-label"]

                if node.get("tag") == "select":
                    node.pop("children", None)
                    node.pop("role", None)
                    node.pop("description", None)

                if node.get("role") == node.get("tag"):
                    del node["role"]

                if (
                    node.get("aria-label")
                    and node.get("placeholder")
                    and node.get("aria-label") == node.get("placeholder")
                ):
                    del node["aria-label"]

                if node.get("role") == "link":
                    del node["role"]
                    if node.get("description"):
                        node["text"] = node["description"]
                        del node["description"]

                if node.get("role") == "textbox":
                    if "id" in element_attributes and element_attributes["id"]:
                        js_code = """
                        (inputParams) => {
                            let referencingElements = [];
                            const referencedElement = document.querySelector(`[aria-labelledby="${inputParams.aria_labelled_by_query_value}"]`);
                            if(referencedElement) {
                                const mmid = referencedElement.getAttribute('mmid');
                                if (mmid) {
                                    return {"mmid": mmid, "tag": referencedElement.tagName.toLowerCase()};
                                }
                            }
                            return null;
                        }
                        """
            else:
                logger.debug(
                    f"No element found with mmid: {mmid}, deleting node: {node}"
                )
                node["marked_for_deletion_by_mm"] = True

    await process_node(accessibility_tree)

    pruned_tree = __prune_tree(accessibility_tree, only_input_fields)

    logger.debug("Reconciliation complete")
    return pruned_tree


async def __cleanup_dom(page: Page):
    """
    Cleans up the DOM by removing injected 'aria-description' attributes and restoring any original 'aria-keyshortcuts'
    from 'orig-aria-keyshortcuts'.
    """
    logger.debug("Cleaning up the DOM's previous injections")
    await page.evaluate("""() => {
        const allElements = document.querySelectorAll('*[mmid]');
        allElements.forEach(element => {
            element.removeAttribute('aria-keyshortcuts');
            const origAriaLabel = element.getAttribute('orig-aria-keyshortcuts');
            if (origAriaLabel) {
                element.setAttribute('aria-keyshortcuts', origAriaLabel);
                element.removeAttribute('orig-aria-keyshortcuts');
            }
        });
    }""")
    logger.debug("DOM cleanup complete")


def __prune_tree(
    node: Dict[str, Any], only_input_fields: bool
) -> Optional[Dict[str, Any]]:
    """
    Recursively prunes a tree starting from `node`, based on pruning conditions and handling of 'unraveling'.

    The function has two main jobs:
    1. Pruning: Remove nodes that don't meet certain conditions, like being marked for deletion.
    2. Unraveling: For nodes marked with 'marked_for_unravel_children', we replace them with their children,
       effectively removing the node and lifting its children up a level in the tree.

    This happens in place, meaning we modify the tree as we go, which is efficient but means you should
    be cautious about modifying the tree outside this function during a prune operation.

    Args:
    - node (Dict[str, Any]): The node we're currently looking at. We'll check this node, its children,
      and so on, recursively down the tree.
    - only_input_fields (bool): If True, we're only interested in pruning input-related nodes (like form fields).
      This lets you narrow the focus if, for example, you're only interested in cleaning up form-related parts
      of a larger tree.

    Returns:
    - Dict[str, Any] | None: The pruned version of `node`, or None if `node` was pruned away. When we 'unravel'
      a node, we directly replace it with its children in the parent's list of children, so the return value
      will be the parent, updated in place.

    Notes:
    - 'marked_for_deletion_by_mm' is our flag for nodes that should definitely be removed.
    - Unraveling is neat for flattening the tree when a node is just a wrapper without semantic meaning.
    - We use a while loop with manual index management to safely modify the list of children as we iterate over it.
    """
    if "marked_for_deletion_by_mm" in node:
        return None

    if "children" in node:
        i = 0
        while i < len(node["children"]):
            child = node["children"][i]
            if "marked_for_unravel_children" in child:
                # Replace the current child with its children
                if "children" in child:
                    node["children"] = (
                        node["children"][:i]
                        + child["children"]
                        + node["children"][i + 1 :]
                    )
                    i += (
                        len(child["children"]) - 1
                    )  # Adjust the index for the new children
                else:
                    # If the node marked for unraveling has no children, remove it
                    node["children"].pop(i)
                    i -= 1  # Adjust the index since we removed an element
            else:
                # Recursively prune the child if it's not marked for unraveling
                pruned_child = __prune_tree(child, only_input_fields)
                if pruned_child is None:
                    # If the child is pruned, remove it from the children list
                    node["children"].pop(i)
                    i -= 1  # Adjust the index since we removed an element
                else:
                    # Update the child with the pruned version
                    node["children"][i] = pruned_child
            i += 1  # Move to the next child

        # After processing all children, if the children array is empty, remove it
        if not node["children"]:
            del node["children"]

    # Apply existing conditions to decide if the current node should be pruned
    return None if __should_prune_node(node, only_input_fields) else node


def __should_prune_node(node: Dict[str, Any], only_input_fields: bool):
    """
    Determines if a node should be pruned based on its 'role' and 'element_attributes'.

    Args:
        node (Dict[str, Any]): The node to be evaluated.
        only_input_fields (bool): Flag indicating whether only input fields should be considered.

    Returns:
        bool: True if the node should be pruned, False otherwise.
    """
    # If the request is for only input fields and this is not an input field, then mark the node for prunning
    if (
        node.get("role") != "WebArea"
        and only_input_fields
        and not (
            node.get("tag") in ("input", "button", "textarea")
            or node.get("role") == "button"
        )
    ):
        return True

    if (
        node.get("role") == "generic"
        and "children" not in node
        and not ("name" in node and node.get("name"))
    ):  # The presence of 'children' is checked after potentially deleting it above
        return True

    if node.get("role") in ["separator", "LineBreak"]:
        return True
    processed_name = ""
    if "name" in node:
        processed_name: str = node.get("name")  # type: ignore
        processed_name = processed_name.replace(",", "")
        processed_name = processed_name.replace(":", "")
        processed_name = processed_name.replace("\n", "")
        processed_name = processed_name.strip()
        if len(processed_name) < 3:
            processed_name = ""

    # check if the node only have name and role, then delete that node
    if (
        len(node) == 2
        and "name" in node
        and "role" in node
        and not (node.get("role") == "text" and processed_name != "")
    ):
        return True
    return False


async def get_node_dom_element(page: Page, mmid: str):
    return await page.evaluate(
        """
        (mmid) => {
            return document.querySelector(`[mmid="${mmid}"]`);
        }
    """,
        mmid,
    )


async def get_element_attributes(page: Page, mmid: str, attributes: List[str]):
    return await page.evaluate(
        """
        (inputParams) => {
            const mmid = inputParams.mmid;
            const attributes = inputParams.attributes;
            const element = document.querySelector(`[mmid="${mmid}"]`);
            if (!element) return null;  // Return null if element is not found

            let attrs = {};
            for (let attr of attributes) {
                attrs[attr] = element.getAttribute(attr);
            }
            return attrs;
        }
    """,
        {"mmid": mmid, "attributes": attributes},
    )


async def get_dom_with_accessibility_info() -> (
    Annotated[
        Optional[Dict[str, Any]],
        "A minified representation of the HTML DOM for the current webpage",
    ]
):
    """
    Retrieves, processes, and minifies the Accessibility tree of the active page in a browser instance.
    Strictly follow the name and role tag for any interaction with the nodes.

    Returns:
    - The minified JSON content of the browser's active page.
    """
    logger.debug("Executing Get Accessibility Tree Command")
    # Create and use the PlaywrightManager
    browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
    page = await browser_manager.get_current_page()
    if page is None:  # type: ignore
        raise ValueError("No active page found")

    return await do_get_accessibility_info(page)


async def do_get_accessibility_info(page: Page, only_input_fields: bool = False):
    """
    Retrieves the accessibility information of a web page and saves it as JSON files.

    Args:
        page (Page): The page object representing the web page.
        only_input_fields (bool, optional): If True, only retrieves accessibility information for input fields.
            Defaults to False.

    Returns:
        Dict[str, Any] or None: The enhanced accessibility tree as a dictionary, or None if an error occurred.
    """
    result = await __inject_attributes(page)
    print(f"__inject_attributes:{result}")
    accessibility_tree: Dict[str, Any] = await page.accessibility.snapshot(
        interesting_only=False
    )  # type: ignore

    with open(
        os.path.join(SOURCE_LOG_FOLDER_PATH, "json_accessibility_dom.json"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write(json.dumps(accessibility_tree, indent=2))
        logger.debug("json_accessibility_dom.json saved")

    await __cleanup_dom(page)
    try:
        enhanced_tree = await __fetch_dom_info(
            page, accessibility_tree, only_input_fields
        )

        logger.debug("Enhanced Accessibility Tree ready")

        with open(
            os.path.join(
                SOURCE_LOG_FOLDER_PATH, "json_accessibility_dom_enriched.json"
            ),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(enhanced_tree, indent=2))
            logger.debug("json_accessibility_dom_enriched.json saved")

        return enhanced_tree
    except Exception as e:
        logger.error(f"Error while fetching DOM info: {e}")
        traceback.print_exc()
        return None
