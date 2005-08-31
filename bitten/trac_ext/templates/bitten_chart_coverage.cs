<chart>
 <chart_type>
  <value>area</value>
  <value>area</value>
 </chart_type>

 <axis_category size="10"
   skip="<?cs var:len(chart.data.0) / 6 ?>" orientation="vertical" />
 <axis_ticks value_ticks="false" category_ticks="true" major_thickness="1"
   minor_thickness="0" major_color="000000" position="outside" />

 <chart_data><?cs
  each:row = chart.data ?><row><?cs
   each:value = row ?><?cs
    if:name(value) == 0 ?><string><?cs
     var:value ?></string><?cs
    else ?><number><?cs
     var:value ?></number><?cs
    /if ?><?cs
   /each ?></row><?cs
  /each ?></chart_data>

 <chart_border color="999999" left_thickness="1" bottom_thickness="1"/>
 <chart_grid_h alpha="5" color="666666" thickness="3"/>
 <chart_pref line_thickness="2" point_shape="none"/>
 <series_color>
  <color>bbbbbb</color>
  <color>9999ff</color>
 </series_color>

 <legend_label layout="vertical" alpha="60"/>
 <legend_rect x="60" y="50" width="10"/>

 <draw>
  <text width="320" height="40" h_align="center" v_align="bottom" size="12" ><?cs
    var:chart.title ?></text>
 </draw>

</chart>
