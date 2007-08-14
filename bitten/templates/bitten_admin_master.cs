<h2>Manage Build Master</h2>

<form class="mod" id="bitten" method="post">

  <fieldset id="config">
    <legend>Configuration Options</legend>
    <div class="field">
      <label>
        <input type="checkbox" id="build_all" name="build_all"
               <?cs if:admin.master.build_all ?> checked="checked"<?cs /if ?> />
        Build all revisions
      </label>
    </div>
    <p class="hint">
      Whether to build older revisions even when a more recent revision has
      already been built.
    </p>
    <div class="field">
      <label>
        <input type="checkbox" id="adjust_timestamps" name="adjust_timestamps"
               <?cs if:admin.master.adjust_timestamps ?> checked="checked"<?cs /if ?> />
        Adjust build timestamps
      </label>
    </div>
    <p class="hint">
      Whether the timestamps of builds should be adjusted to be close to the
      timestamps of the corresponding changesets.
    </p>
    <hr />
    <div class="field">
      <label>
        Connection timeout for build slaves:
        <input type="text" id="slave_timeout" name="slave_timeout"
               value="<?cs var:admin.master.slave_timeout ?>" size="5" />
      </label>
    </div>
    <p class="hint">
      The timeout in milliseconds after which a build started by a slave is
      considered aborted, in case there has been no activity from that slave
      in that time.
    </p>
  </fieldset>

  <div class="buttons">
    <input type="submit" value="Apply changes"/>
  </div>
</form>
