Field rules: "op" is one word — create, update, or resolve. Each op carries
EXACTLY its own fields:
  create: key + text + evidence + reason
  update: id + text + reason
  resolve: id + reason