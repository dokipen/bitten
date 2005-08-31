<?cs include:"header.cs" ?>
 <div id="ctxtnav" class="nav"></div>
 <div id="content" class="build">
  <h1><?cs var:title ?></h1><?cs

  if:page.mode == 'overview' ?><?cs
   each:config = configs ?>
    <h2><a href="<?cs var:config.href ?>"><?cs var:config.label ?></a></h2><?cs
    if:config.description ?><div class="description"><?cs
     var:config.description ?></div><?cs
    /if ?><?cs
   /each ?><?cs
   if:config.can_create ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="new" />
     <input type="submit" value="Add configuration" />
    </div></form></div><?cs
   /if ?></div><?cs

  elif:page.mode == 'edit_config' ?>
   <form class="config" method="post" action="">
    <table summary=""><tr>
     <td class="name"><label>Name:<br />
      <input type="text" name="name" value="<?cs var:config.name ?>" />
     </label></td>
     <td class="label"><label>Label (for display):<br />
      <input type="text" name="label" size="32" value="<?cs
        var:config.label ?>" />
     </label></td>
    </tr><tr>
     <td colspan="2"><fieldset class="iefix">
      <label for="description">Description (you may use <a tabindex="42" href="<?cs
        var:trac.href.wiki ?>/WikiFormatting">WikiFormatting</a> here):</label>
      <p><textarea id="description" name="description" class="wikitext" rows="5" cols="78"><?cs
        var:config.description ?></textarea></p>
      <script type="text/javascript" src="<?cs
        var:htdocs_location ?>js/wikitoolbar.js"></script>
     </fieldset></td>
    </tr></table>
    <fieldset id="recipe">
     <legend>Build Recipe</legend>
     <textarea id="recipe" name="recipe" rows="8" cols="78"><?cs
       var:config.recipe ?></textarea>
    </fieldset>
    <fieldset id="repos">
     <legend>Repository Mapping</legend>
     <table summary=""><tr>
      <th><label for="path">Path:</label></th>
      <td><input type="text" name="path" size="48" value="<?cs
        var:config.path ?>" /></td>
     </tr></table>
    </fieldset>
    <div class="buttons">
     <input type="hidden" name="action" value="<?cs
       if:config.exists ?>edit<?cs else ?>new<?cs /if ?>" />
     <input type="submit" value="<?cs
       if:config.exists ?>Save changes<?cs else ?>Create<?cs /if ?>" />
     <input type="submit" name="cancel" value="Cancel" />
    </div>
   </form><?cs
   if:config.exists ?><div class="platforms">
     <form class="platforms" method="post" action="">
      <h2>Target Platforms</h2><?cs
       if:len(config.platforms) ?><ul><?cs
        each:platform = config.platforms ?>
         <li><input type="checkbox" name="delete_platform" value="<?cs
          var:platform.id ?>"> <a href="<?cs
          var:platform.href ?>"><?cs var:platform.name ?></a>
         </li><?cs
        /each ?></ul><?cs
       /if ?>
      <div class="buttons">
       <input type="submit" name="new" value="Add target platform" />
       <input type="submit" name="delete" value="Delete selected platforms" />
      </div>
     </form>
    </div><?cs
   /if ?><?cs

  elif:page.mode == 'view_config' ?><?cs
   if:config.can_modify ?><form id="prefs" method="post" class="activation"><?cs
    if:!config.active ?><div class="help">This build configuration is currently
     inactive.<br /> No builds will be initiated for this configuration<br />
     until it is activated.</div><?cs
    else ?><div class="help">This configuration is currently active.</div><?cs
    /if ?>
    <div class="buttons">
     <input type="hidden" name="action" value="edit" /><?cs
     if:config.active ?>
      <input type="submit" name="deactivate" value="Deactivate" /><?cs
     else ?>
      <input type="submit" name="activate" value="Activate" /><?cs
     /if ?>
    </div></form><?cs
   /if ?>
   <ul><li>Path: <?cs if:config.path ?><a href="<?cs
     var:config.browser_href ?>"><?cs
     var:config.path ?></a></li><?cs /if ?></ul><?cs
   if:config.description ?><div class="description"><?cs
     var:config.description ?></div><?cs
   /if ?>
   
   <div id="charts"><?cs
    each:chart = config.charts ?>
     <object type="application/x-shockwave-flash" width="320" height="240" data="<?cs
      var:chrome.href ?>/bitten/charts.swf">
      <param name="FlashVars" value="library_path=<?cs
        var:chrome.href ?>/bitten/charts&amp;xml_source=<?cs
        var:chart.href ?>" />
      <param name="wmode" value="transparent" />
     </object><br /><?cs
    /each ?>
   </div>
   
   <?cs
   if:config.can_modify ?>
    <div class="buttons">
     <form method="get" action=""><div>
      <input type="hidden" name="action" value="edit" />
      <input type="submit" value="Edit configuration" />
     </div></form>
    </div><?cs
   /if ?><?cs
   if:len(config.platforms) ?>
    <table class="listing" id="builds"><thead><tr>
     <th class="chgset" abbrev="Changeset">Chgset</th><?cs
     each:platform = config.platforms ?><th><?cs var:platform.name ?><?cs
     /each ?>
    </tr></thead><?cs
    if:len(config.builds) ?><tbody><?cs
     each:rev = config.builds ?><tr>
      <th class="chgset" scope="row"><a href="<?cs
        var:rev.href ?>" title="View Changeset">[<?cs
        var:name(rev) ?>]</a></th><?cs
      each:platform = config.platforms ?><?cs
       if:len(rev[platform.id]) ?><?cs
        with:build = rev[platform.id] ?><td class="<?cs
         var:build.cls ?>"><a href="<?cs
         var:build.href ?>" title="View build results"><?cs
         var:build.slave.name ?></a> (<?cs
         var:build.slave.os ?> <?cs
         var:build.slave.os.version ?>)<br /><?cs
         if:build.status == 'in progress' ?>started <?cs
          var:build.started_delta ?> ago<?cs
         else ?>took <?cs
          var:build.duration ?></td><?cs
         /if ?><?cs
        /with ?><?cs
       else ?><td>&mdash;</td><?cs
       /if ?><?cs
      /each ?></tr><?cs
     /each ?></tbody><?cs
    /if ?></table><?cs
   /if ?></div><br style="clear: right"/><?cs

  elif:page.mode == 'edit_platform' ?>
   <form class="platform" method="post" action="">
    <div class="field"><label>Name:<br />
     <input type="text" name="name" value="<?cs var:platform.name ?>" />
    </label></div>
    <h2>Rules</h2>
    <table><thead><tr>
     <th>Property name</th><th>Match pattern</th>
    </tr></thead><tbody><?cs
     each:rule = platform.rules ?><tr>
      <td><input type="text" name="property_<?cs var:name(rule) ?>" value="<?cs
       var:rule.property ?>" /></td>
      <td><input type="text" name="pattern_<?cs var:name(rule) ?>" value="<?cs
       var:rule.pattern ?>" /></td>
      <td><input type="submit" name="rm_rule_<?cs
        var:name(rule) ?>" value="-" /><input type="submit" name="add_rule_<?cs
        var:name(rule) ?>" value="+" />
      </td>
     </tr><?cs /each ?>
    </tbody></table>
    <div class="buttons">
     <form method="get" action=""><div>
     <input type="hidden" name="action" value="<?cs
       if:platform.exists ?>edit<?cs else ?>new<?cs /if ?>" />
      <input type="hidden" name="platform" value="<?cs
       var:platform.id ?>" />
      <input type="submit" value="<?cs
       if:platform.exists ?>Save changes<?cs else ?>Add platform<?cs
       /if ?>" />
      <input type="submit" name="cancel" value="Cancel" />
     </div></form>
    </div>
   </form><?cs

  /if ?>
 </div>
<?cs include:"footer.cs" ?>
