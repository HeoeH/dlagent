from playwright.async_api import Page
from typing_extensions import Annotated, Optional

from agentq.core.web_driver.playwright import PlaywrightManager


async def get_web_element_rect(
    webpage: Optional[Page] = None,
) -> Annotated[str, "Returns the rects(SoM) and web elements of the page"]:
    """
    Returns the rects(SoM) and web elements  of the current page

    Parameters:

    Returns:
    - Full rects(SoM) and web elements
    """

    try:
        # Create and use the PlaywrightManager
        browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
        if webpage is not None:
            page = webpage
        else:
            page = await browser_manager.get_current_page()

        if not page:
            raise ValueError("No active page found. OpenURL command opens a new page.")

        await page.wait_for_load_state("domcontentloaded")

        # Get the URL of the current page
        try:
            if fix_color:
                selected_function = "getFixedColor"
            else:
                 selected_function = "getRandomColor"

            js_script = """
            let labels = [];

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

                        return elAtCenter === element || element.contains(elAtCenter) 
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
                            (element.tagName === "IFRAME" || element.tagName === "VIDEO" || element.tagName === "LI" || element.tagName === "TD" || element.tagName === "OPTION")
                        ,
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

                    // Only keep inner clickable items
                    // first delete button inner clickable items
                    const buttons = Array.from(document.querySelectorAll('button, a, input[type="button"], div[role="button"]'));

                    //items = items.filter(x => !buttons.some(y => y.contains(x.element) && !(x.element === y) ));
                    items = items.filter(x => !buttons.some(y => items.some(z => z.element === y) && y.contains(x.element) && !(x.element === y) ));
                    items = items.filter(x => 
                        !(x.element.parentNode && 
                        x.element.parentNode.tagName === 'SPAN' && 
                        x.element.parentNode.children.length === 1 && 
                        x.element.parentNode.getAttribute('role') &&
                        items.some(y => y.element === x.element.parentNode)));

                    items = items.filter(x => !items.some(y => x.element.contains(y.element) && !(x == y)))

                    // Function to generate random colors
                    function getRandomColor(index) {
                        var letters = '0123456789ABCDEF';
                        var color = '#';
                        for (var i = 0; i < 6; i++) {
                        color += letters[Math.floor(Math.random() * 16)];
                        }
                        return color;
                    }

                    function getFixedColor(index) {
                        var color = '#000000'
                        return color
                    }
                    //function getFixedColor(index){
                    //    var colors = ['#FF0000', '#00FF00', '#0000FF', '#000000']; // Red, Green, Blue, Black
                    //    return colors[index % 4];
                    //}
                    

                    // Lets create a floating border on top of these elements that will always be visible
                    items.forEach(function(item, index) {
                        item.rects.forEach((bbox) => {
                        newElement = document.createElement("div");
                        var borderColor = COLOR_FUNCTION(index);
                        newElement.style.outline = `2px dashed ${borderColor}`;
                        newElement.style.position = "fixed";
                        newElement.style.left = bbox.left + "px";
                        newElement.style.top = bbox.top + "px";
                        newElement.style.width = bbox.width + "px";
                        newElement.style.height = bbox.height + "px";
                        newElement.style.pointerEvents = "none";
                        newElement.style.boxSizing = "border-box";
                        newElement.style.zIndex = 2147483647;
                        // newElement.style.background = `${borderColor}80`;
                        
                        // Add floating label at the corner
                        var label = document.createElement("span");
                        label.textContent = index;
                        label.style.position = "absolute";
                        //label.style.top = "-19px";
                        label.style.top = Math.max(-19, -bbox.top) + "px";
                        //label.style.left = "0px";
                        label.style.left = Math.min(Math.floor(bbox.width / 5), 2) + "px";
                        label.style.background = borderColor;
                        label.style.color = "white";
                        label.style.padding = "2px 4px";
                        label.style.fontSize = "12px";
                        label.style.borderRadius = "2px";
                        newElement.appendChild(label);
                        
                        document.body.appendChild(newElement);
                        labels.push(newElement);
                        // item.element.setAttribute("-ai-label", label.textContent);
                        });
                    })

                    // For the first way
                    // return [labels, items.map(item => ({
                    //     rect: item.rects[0] // assuming there's at least one rect
                    // }))];

                    // For the second way
                    return [labels, items]
                }

            // Call the markPage function and return its result
            markPage();
            """.replace("COLOR_FUNCTION", selected_function)

            # 获取 web 元素的矩形和其他属性  
            rects, items_raw = await page.evaluate(js_script)  

            format_ele_text = []  
            for web_ele_id in range(len(items_raw)):  

                element_info = items_raw[web_ele_id]
                ele_tag_name = element_info['tagName']
                ele_type = element_info['type']
                ele_aria_label = element_info['ariaLabel']
                # print(f"tagname:{ele_tag_name}")
                # print(f"type:{ele_type}")
                # print(f"ariaLabel:{ele_aria_label}")

                # 安全地访问 tag_name  
                # ele_tag_name = items_raw[web_ele_id]['element'].tag_name  
                # ele_type = items_raw[web_ele_id]['element'].get_attribute("type")  
                # ele_aria_label = items_raw[web_ele_id]['element'].get_attribute("aria-label")  
                label_text = items_raw[web_ele_id]['text']  
                input_attr_types = ['text', 'search', 'password', 'email', 'tel']  
                
                if not label_text:  
                    if (ele_tag_name.lower() == 'input' and ele_type in input_attr_types) or \
                    ele_tag_name.lower() == 'textarea' or \
                    (ele_tag_name.lower() == 'button' and ele_type in ['submit', 'button']):  
                        if ele_aria_label:  
                            format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{ele_aria_label}\";")  
                        else:  
                            format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";")  
                elif label_text and len(label_text) < 200:  
                    if not ("<img" in label_text and "src=" in label_text):  
                        if ele_tag_name in ["button", "input", "textarea"]:  
                            if ele_aria_label and (ele_aria_label != label_text):  
                                format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\", \"{ele_aria_label}\";")  
                            else:  
                                format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";")  
                        else:  
                            if ele_aria_label and (ele_aria_label != label_text):  
                                format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\", \"{ele_aria_label}\";")  
                            else:  
                                format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\";")  

            format_ele_text = '\t'.join(format_ele_text)  
            return rects, [web_ele['element'] for web_ele in items_raw], format_ele_text
        except Exception as e:
            raise ValueError(
                "No SoM marked.."
            ) from e
    except Exception as e:
            raise ValueError(
                "No SoM marked.."
            ) from e
  
