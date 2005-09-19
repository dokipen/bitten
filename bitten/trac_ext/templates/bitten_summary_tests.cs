<h3>Test Results</h3>
<table class="listing tests">
 <thead><tr>
  <th>Test Fixture</th><th>Total</th>
  <th>Failures</th><th>Errors</th>
 </tr></thead>
 <tbody><?cs
 each:item = data ?><tr><td><a href="<?cs
  var:item.href ?>"><?cs var:item.name ?></a></td><td><?cs
  var:#item.num_success + #item.num_failure + #item.num_error ?></td><td><?cs
  var:item.num_failure ?></td><td><?cs
  var:item.num_error ?></td></tr><?cs
 /each ?></tbody>
</table>
