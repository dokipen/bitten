<h2>Manage Build Configurations</h2><?cs

if admin.config.name ?>
 <form class="mod" id="modconfig" method="post">
  <table class="form" summary=""><tr>
   <td class="name"><label>Name:<br />
    <input type="text" name="name" value="<?cs var:admin.config.name ?>" />
   </label></td>
   <td class="label"><label>Label (for display):<br />
    <input type="text" name="label" size="32" value="<?cs
      var:admin.config.label ?>" />
   </label></td>
  </tr><tr>
   <td colspan="2"><fieldset class="iefix">
    <label for="description">Description (you may use <a tabindex="42" href="<?cs
      var:trac.href.wiki ?>/WikiFormatting">WikiFormatting</a> here):</label>
    <p><textarea id="description" name="description" class="wikitext" rows="3" cols="65"><?cs
      var:admin.config.description ?></textarea></p>
    <script type="text/javascript" src="<?cs
      var:chrome.href ?>/common/js/wikitoolbar.js"></script>
   </fieldset></td>
  </tr><tr>
   <td colspan="2"><fieldset class="iefix">
    <label for="recipe">Recipe:</label>
    <p><textarea id="recipe" name="recipe" rows="8" cols="78"><?cs
     var:admin.config.recipe ?></textarea></p>
   </fieldset></td>
  </tr></table>
  <fieldset id="repos">
   <legend>Repository Mapping</legend>
   <table class="form" summary=""><tr>
    <th><label for="path">Path:</label></th>
    <td colspan="3"><input type="text" name="path" size="48" value="<?cs
      var:admin.config.path ?>" /></td>
   </tr><tr>
    <th><label for="min_rev">Oldest revision:</label></th>
    <td><input type="text" name="min_rev" size="8" value="<?cs
      var:admin.config.min_rev ?>" /></td>
    <th><label for="min_rev">Youngest revision:</label></th>
    <td><input type="text" name="max_rev" size="8" value="<?cs
      var:admin.config.max_rev ?>" /></td>
   </table>
  </fieldset>
  <div class="buttons">
   <input type="submit" name="cancel" value="Cancel" />
   <input type="submit" name="save" value="Save" />
  </div>
  <div class="platforms">
   <h3>Target Platforms</h3>
   <table class="listing" id="platformlist">
    <thead>
     <tr><th class="sel">&nbsp;</th><th>Name</th><th>Rules</th></tr>
    </thead><?cs each:platform = admin.config.platforms ?><tr>
      <td class="sel"><input type="checkbox" name="sel" value="<?cs
        var:platform.id ?>" /></td>
      <td class="name"><a href="<?cs var:platform.href?>"><?cs
        var:platform.name ?></a></td>
      <td class="rules"><?cs if:len(platform.rules) ?><ul><?cs
       each:rule = platform.rules ?><li><code>
        <strong><?cs var:rule.property ?></strong> ~= <?cs var:rule.pattern ?>
       </code></li><?cs
       /each ?></ul><?cs
      /if ?></td>
     </tr><?cs
    /each ?>
   </table>
   <div class="buttons">
    <input type="submit" name="new" value="Add platform" />
    <input type="submit" name="remove" value="Delete selected platforms" />
   </div>
  </div>
 </form><?cs

elif len(admin.platform) ?>
 <form class="mod" id="modplatform" method="post">
  <div class="field"><label>Target Platform:
   <input type="text" name="name" value="<?cs var:admin.platform.name ?>" />
  </label></div>
  <fieldset>
   <legend>Rules</legend>
   <table><thead><tr>
    <th>Property name</th><th>Match pattern</th>
   </tr></thead><tbody><?cs
    each:rule = admin.platform.rules ?><tr>
     <td><input type="text" name="property_<?cs var:name(rule) ?>" value="<?cs
      var:rule.property ?>" /></td>
     <td><input type="text" name="pattern_<?cs var:name(rule) ?>" value="<?cs
      var:rule.pattern ?>" /></td>
     <td><input type="submit" name="add_rule_<?cs
       var:name(rule) ?>" value="+" /><input type="submit" name="rm_rule_<?cs
       var:name(rule) ?>" value="-" />
     </td>
    </tr><?cs /each ?>
   </tbody></table>
  </fieldset>
  <p class="help">
   The property name can be any of a set of standard default properties, or
   custom properties defined in slave configuration files. The default
   properties are:
  </p>
  <dl class="help">
   <dt><code>os<code>:</dt>
   <dd>The name of the operating system (for example "Darwin")</dd>
   <dt><code>family<code>:</dt>
   <dd>The type of operating system (for example "posix" or "nt")</dd>
   <dt><code>version<code>:</dt>
   <dd>The operating system version (for example "8.10.1)</dd>
   <dt><code>machine<code>:</dt>
   <dd>The hardware architecture (for example "i386")</dd>
   <dt><code>processor<code>:</dt>
   <dd>The CPU model (for example "i386", this may be empty or the same as for
     <code>machine</code>)</dd>
   <dt><code>name<code>:</dt>
   <dd>The name of the slave</dd>
   <dt><code>ipnr<code>:</dt>
   <dd>The IP address of the slave</dd>
  </dl>
  <p class="help">The match pattern is a regular expression.</p>
  <div class="buttons">
   <form method="get" action=""><div>
    <input type="hidden" name="<?cs
     if:admin.platform.exists ?>edit<?cs else ?>new<?cs /if ?>" value="" />
    <input type="hidden" name="platform" value="<?cs
     var:admin.platform.id ?>" />
    <input type="submit" name="cancel" value="Cancel" />
    <?cs if:admin.platform.exists ?>
     <input type="submit" name="save" value="Save" />
    <?cs else ?>
     <input type="submit" name="add" value="Add" />
    <?cs /if ?>
   </div></form>
  </div>
 </form><?cs

else ?>
 <form class="addnew" id="addcomp" method="post">
  <fieldset>
   <legend>Add Configuration:</legend>
   <table summary=""><tr>
    <td class="name"><div class="field"><label>Name:<br />
     <input type="text" name="name" size="12" />
    </label></div></td>
    <td class="label"><div class="field"><label>Label:<br />
     <input type="text" name="label" size="22" />
    </label></div></td>
   </tr><tr>
     <td class="path" colspan="2"><div class="field">
      <label>Path:<br /><input type="text" name="path" size="32" /></label>
     </div>
   </tr></table>
   <div class="buttons">
    <input type="submit" name="add" value="Add">
   </div>
  </fieldset>
 </form>

 <form method="POST">
  <table class="listing" id="configlist">
   <thead>
    <tr><th class="sel">&nbsp;</th><th>Name</th>
    <th>Path</th><th>Active</th></tr>
   </thead><?cs each:config = admin.configs ?>
    <tr>
     <td class="sel"><input type="checkbox" name="sel" value="<?cs
       var:config.name ?>" /></td>
     <td class="name"><a href="<?cs var:config.href?>"><?cs
       var:config.label ?></a></td>
     <td class="path"><code><?cs var:config.path ?></code></td>
     <td class="active"><input type="checkbox" name="active" value="<?cs
       var:config.name ?>"<?cs
       if:config.active ?> checked="checked" <?cs /if ?>></td>
    </tr><?cs
   /each ?>
  </table>
  <div class="buttons">
   <input type="submit" name="remove" value="Remove selected items" />
   <input type="submit" name="apply" value="Apply changes" />
  </div>
 </form><?cs

/if ?>
