<h3>Test Results</h3>
<table class="listing tests">
 <thead><tr>
  <th>Test Fixture</th><th>Total</th>
  <th>Failures</th><th>Errors</th>
 </tr></thead>
 <tbody><?cs
 each:item = data ?><tr><td><a href="<?cs
  var:item.href ?>"><?cs var:item.name ?></a></td><td><?cs
  var:#item.success + #item.failures + #item.errors ?></td><td><?cs
  var:item.failures ?></td><td><?cs
  var:item.errors ?></td></tr><?cs
 /each ?></tbody>
</table>
