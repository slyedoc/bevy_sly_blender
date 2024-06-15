
import bpy

class MISSING_TYPES_UL_List(bpy.types.UIList):
    """Missing components UIList.""" 

    use_filter_name_reverse: bpy.props.BoolProperty(
        name="Reverse Name",
        default=False,
        options=set(),
        description="Reverse name filtering",
    ) # type: ignore

    use_order_name = bpy.props.BoolProperty(name="Name", default=False, options=set(),
                                            description="Sort groups by their name (case-insensitive)")

    def filter_items__(self, context, data, propname): 
        """Filter and order items in the list.""" 
        # We initialize filtered and ordered as empty lists. Notice that # if all sorting and filtering is disabled, we will return # these empty. 
        filtered = [] 
        ordered = [] 
        items = getattr(data, propname)

        helper_funcs = bpy.types.UI_UL_list


        print("filter, order", items, self, dict(self))
        if self.filter_name:
            print("ssdfs", self.filter_name)
            filtered= helper_funcs.filter_items_by_name(self.filter_name, self.bitflag_filter_item, items, "long_name", reverse=self.use_filter_name_reverse)

        if not filtered:
            filtered = [self.bitflag_filter_item] * len(items)

        if self.use_order_name:
            ordered = helper_funcs.sort_items_by_name(items, "name")
        

        return filtered, ordered 


    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index): 
        if self.layout_type in {'DEFAULT', 'COMPACT'}: 
            row = layout.row()
            #row.enabled = False
            #row.alert = True
            row.prop(item, "long_name", text="")

        elif self.layout_type in {'GRID'}: 
            layout.alignment = 'CENTER' 
            row = layout.row()
            row.prop(item, "long_name", text="")
