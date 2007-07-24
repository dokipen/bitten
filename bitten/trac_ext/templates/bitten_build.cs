<?cs include:"header.cs" ?>
 <script type="text/javascript" src="<?cs
   var:chrome.href ?>/bitten/tabset.js"></script>
 <div id="ctxtnav" class="nav"></div>
 <div id="content" class="build">
  <h1><?cs var:title ?></h1>
  <dl id="overview">
   <dt class="config">Configuration:</dt>
   <dd class="config"><a href="<?cs var:build.config.href ?>"><?cs
    var:build.config.name ?></a>
   </dd>
   <dt class="trigger">Triggered by:</dt>
   <dd class="trigger">Changeset <a href="<?cs
    var:build.chgset_href ?>">[<?cs var:build.rev ?>]</a> by <?cs
    var:build.chgset_author ?>
   </dd>
   <dt class="slave">Built by:</dt>
   <dd class="slave"><code><?cs var:build.slave.name ?></code> (<?cs
    var:build.slave.ipnr ?>)
   </dd>
   <dt class="os">Operating system:</dt>
   <dd><?cs var:build.slave.os.name ?> <?cs var:build.slave.os.version ?> (<?cs
    var:build.slave.os.family ?>)
   </dd><?cs
   if:build.slave.machine ?>
    <dt class="machine">Hardware:</dt>
    <dd class="machine"><?cs
     var:build.slave.machine ?><?cs
     if:build.slave.processor ?> (<?cs
      var:build.slave.processor ?>)<?cs
     /if ?>
    </dd><?cs
   /if ?>
   <dt class="time">Started:</dt>
   <dd class="time"><?cs var:build.started ?> (<?cs
    var:build.started_delta ?> ago)
   </dd>
   <dt class="duration">Took:</dt>
   <dd class="duration"><?cs
    var:build.duration ?>
   </dd>
  </dl><?cs
  if:build.can_delete ?>
   <div class="buttons">
    <form method="post" action=""><div>
     <input type="hidden" name="action" value="invalidate" />
     <input type="submit" value="Invalidate build" />
    </div></form>
   </div><?cs
  /if ?><?cs
  each:step = build.steps ?>
   <h2 class="step" id="step_<?cs var:step.name ?>"><?cs var:step.name ?> (<?cs
     var:step.duration ?>)</h2><?cs
   if:len(step.errors) ?>
    <div class="errors">
     <h3>Errors</h3><ul><?cs
     each:error = step.errors ?><li><?cs var:error ?></li><?cs
     /each ?></ul>
    </div><?cs
   /if ?><p><?cs var:step.description ?></p>
   <div id="<?cs var:step.name ?>_tabs">
    <div class="tab"><h3>Log</h3><div class="log"><?cs
     each:item = step.log ?><code class="<?cs var:item.level ?>"><?cs
      var:item.message ?></code><br /><?cs
     /each ?></div>
    </div><?cs
    each:report = step.reports ?><?cs
     if:report.summary ?>
      <div class="tab report <?cs var:report.type ?>">
       <?cs var:report.summary ?>
      </div><?cs
     /if ?><?cs
    /each ?>
   </div>
   <script type="text/javascript">
     makeTabSet(document.getElementById("<?cs var:step.name ?>_tabs"));
   </script><?cs
  /each ?>
 </div>
<?cs include:"footer.cs" ?>
