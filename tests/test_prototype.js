class ProtoMethodDemo {
  constructor(name) {
    this.name = name;

    // Instance function property: each instance gets its own function object
    this.instanceHello = function () {
      return `instanceHello from ${this.name}`;
    };
  }

  // Prototype method: shared by all instances via ProtoMethodDemo.prototype
  protoHello() {
    return `protoHello from ${this.name}`;
  }
}

const a = new ProtoMethodDemo("A");
const b = new ProtoMethodDemo("B");

console.log("=== Where do methods live? ===");
console.log("a.hasOwnProperty('protoHello'):", a.hasOwnProperty("protoHello"));       // false
console.log("a.hasOwnProperty('instanceHello'):", a.hasOwnProperty("instanceHello")); // true
console.log("protoHello is from prototype:",
            a.protoHello === ProtoMethodDemo.prototype.protoHello); // true

console.log(a.protoHello === ProtoMethodDemo.prototype.protoHello); // true
console.log(Object.getPrototypeOf(a) === ProtoMethodDemo.prototype); // true



console.log("\n=== Are methods shared? ===");
console.log("a.protoHello === b.protoHello:", a.protoHello === b.protoHello);         // true (shared)
console.log("a.instanceHello === b.instanceHello:", a.instanceHello === b.instanceHello); // false (per instance)

console.log("\n=== Prototype linkage ===");
console.log("Object.getPrototypeOf(a) === ProtoMethodDemo.prototype:",
            Object.getPrototypeOf(a) === ProtoMethodDemo.prototype); // true

console.log("\n=== Property lookup order (instance first, then prototype) ===");
console.log("a.protoHello():", a.protoHello());       // uses prototype method
console.log("a.instanceHello():", a.instanceHello()); // uses instance property

// Override: define a property on instance with same name as prototype method
a.protoHello = function () {
  return "OVERRIDDEN protoHello on instance A";
};

console.log("\n=== After overriding a.protoHello on the instance ===");
console.log("a.hasOwnProperty('protoHello'):", a.hasOwnProperty("protoHello")); // true now
console.log("a.protoHello():", a.protoHello()); // instance version
console.log("b.protoHello():", b.protoHello()); // still prototype version
