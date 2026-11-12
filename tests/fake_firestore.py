"""Testlar uchun minimal xotiradagi Firestore (faqat bot ishlatadigan qismlar)."""


class Snap:
    def __init__(self, ref, data):
        self.reference = ref
        self.id = ref.id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class Doc:
    def __init__(self, store, path):
        self.store, self.path = store, path
        self.id = path.rsplit('/', 1)[-1]

    def get(self, transaction=None):
        return Snap(self, self.store.get(self.path))

    def update(self, data):
        if self.path not in self.store:
            raise KeyError(f"no document {self.path}")
        doc = self.store[self.path]
        for k, v in data.items():
            if type(v).__name__ == 'Increment':
                doc[k] = (doc.get(k) or 0) + v.value
            else:
                doc[k] = v

    def collection(self, name):
        return Col(self.store, f"{self.path}/{name}")


class Query:
    def __init__(self, col, filters, limit=None):
        self.col, self.filters, self._limit = col, filters, limit

    def where(self, field, op, value):
        assert op == '=='
        return Query(self.col, self.filters + [(field, value)], self._limit)

    def limit(self, n):
        return Query(self.col, self.filters, n)

    def stream(self):
        prefix = self.col.path + '/'
        out = []
        for path, data in sorted(self.col.store.items()):
            rest = path[len(prefix):] if path.startswith(prefix) else None
            if rest is None or '/' in rest:
                continue
            if all(data.get(f) == v for f, v in self.filters):
                out.append(Snap(Doc(self.col.store, path), data))
        return out[:self._limit] if self._limit else out


class Col(Query):
    def __init__(self, store, path):
        self.store, self.path = store, path
        super().__init__(self, [])

    def document(self, doc_id):
        return Doc(self.store, f"{self.path}/{doc_id}")


class Writer:
    """Transaction va batch uchun umumiy yozuvchi."""

    def __init__(self, store):
        self.store = store

    def create(self, ref, data):
        if ref.path in self.store:
            raise ValueError(f"already exists: {ref.path}")
        self.store[ref.path] = dict(data)

    def set(self, ref, data):
        self.store[ref.path] = dict(data)

    def update(self, ref, data):
        ref.update(data)

    def delete(self, ref):
        self.store.pop(ref.path, None)

    def commit(self):
        pass


class Db:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return Col(self.store, name)

    def transaction(self):
        return Writer(self.store)

    def batch(self):
        return Writer(self.store)
