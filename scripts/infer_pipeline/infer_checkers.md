

### Available Checkers 

(infer ce1ba6a) 

https://github.com/facebook/infer/blob/ce1ba6a/infer/src/base/Checker.ml#L63


| cmd option                    | checker type in code      | enabled_by_default | language                  |
| ----------------------------- | ------------------------- | ------------------ | ------------------------- |
| --annotation-reachability     | AnnotationReachability    | false              | clang, java               |
| --biabduction                 | Biabduction               | true               | clang, java               |
| --bufferoverrun               | BufferOverrun             | false              | clang, java               |
| --class-loads                 | ClassLoads                | false              | java                      |
| --cost                        | Cost                      | false              | clang, java               |
| --eradicate                   | Eradicate                 | false              | java                      |
| --fragment-retains-view       | FragmentRetainsView       | true               | java                      |
| --immutable-cast              | ImmutableCast             | false              | java                      |
| --impurity                    | Impurity                  | false              | clang, java (experimental)|
| --inefficient-keyset-iterator | InefficientKeysetIterator | true               | java                      |
| --linters                     | Linters                   | true               | clang                     |
| --litho-required-props        | LithoRequiredProps        | false              | java (experimental)       |
| --liveness                    | Liveness                  | true               | clang                     |
| --loop-hoisting               | LoopHoisting              | false              | clang, java               |
| --eradicate (for now)         | NullsafeDeprecated        | false              | java                      |
| --printf-args                 | PrintfArgs                | false              | java                      |
| --pulse                       | Pulse                     | false              | clang (experimental)      |
| --purity                      | Purity                    | false              | clang, java (experimental)|
| --quandary                    | Quandary                  | false              | clang, java               |
| --racerd                      | RacerD                    | true               | clang, java               |
| --resource-leak               | ResourceLeak              | false              | java (toy support)        |
| --siof                        | SIOF                      | true               | clang                     |
| --self_in_block               | SelfInBlock               | true               | clang                     |     
| --starvation                  | Starvation                | true               | clang, java               | 
| --uninit                      | Uninit                    | true               | clang                     | 


* **AnnotationReachability**: reachability specs required. https://github.com/facebook/infer/blob/master/infer/tests/codetoanalyze/cpp/annotation-reachability/Makefile#L11

* **Eradicate**: a type checker for @Nullable annotations for Java. https://github.com/facebook/infer/blob/master/website/docs/01-eradicate.md

* **Purity**: purity analysis: if the execution of a method may change the visible state 

* **Quandary**: the quandary taint analysis: have to specify source and sink in `.inferconfig` according to https://github.com/facebook/infer/issues/1038.

* **SelfInBlock**: incorrect uses of when Objective-C blocks capture self

* **Uninit**: use of uninitialized values

* **FragmentRetainsView**: This error type is Android-specific. It fires when a Fragment type fails to nullify one or more of its declared View fields in onDestroyView.

----

### Additional Checkers To Be Enabled

```shell
--bufferoverrun --pulse --no-linters --no-fragment-retains-view --no-inefficient-keyset-iterator --no-self_in_block
```
